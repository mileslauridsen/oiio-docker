#!/usr/bin/env python3
"""Build one platform year twice from isolated copies without cache, and compare binaries, filesystems, and digests."""

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
IGNORED = shutil.ignore_patterns(".git", ".idea", "__pycache__", ".pytest_cache")
# Paths Docker creates or mounts in every container.
CONTAINER_RUNTIME_PATHS = (".dockerenv", "dev", "proc", "sys", "run", "etc/hostname", "etc/hosts", "etc/resolv.conf",
                           "etc/mtab")

# Runs in the image: hash every ELF file under /opt/vfx (executables, shared libraries, Python extensions) and every
# system library they load.
BINARY_HASHES = r"""
import hashlib, json, os, re, subprocess
paths, system = [], set()
for root, _dirs, files in os.walk("/opt/vfx"):
    for name in files:
        path = os.path.join(root, name)
        if os.path.islink(path):
            continue
        with open(path, "rb") as handle:
            if handle.read(4) != b"\x7fELF":
                continue
        paths.append(path)
        env = dict(os.environ, LD_LIBRARY_PATH=root) if root.endswith(".libs") else None
        output = subprocess.run(["ldd", path], stdout=subprocess.PIPE, universal_newlines=True, env=env).stdout
        system.update(match for match in re.findall(r"=> (/\S+)", output) if not match.startswith("/opt/vfx/"))
result = {}
for path in sorted(paths) + sorted(system):
    with open(os.path.realpath(path), "rb") as handle:
        result[path] = hashlib.sha256(handle.read()).hexdigest()
print(json.dumps(result))
"""


def run(command, check=True, **kwargs):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, **kwargs)
    if check and result.returncode:
        raise RuntimeError("command failed (%s):\n%s" % (" ".join(command), result.stdout))
    return result


def image_identity(image):
    """Return the local image ID, the config digest from the saved config JSON, and the layer diff IDs."""
    inspected = json.loads(run(["docker", "image", "inspect", image]).stdout)[0]
    with tempfile.TemporaryDirectory(prefix="oiio-image-config-") as temporary:
        archive_path = pathlib.Path(temporary) / "image.tar"
        run(["docker", "image", "save", "--output", str(archive_path), image])
        with tarfile.open(archive_path, mode="r:") as archive:
            manifest = json.load(archive.extractfile("manifest.json"))
            config_bytes = archive.extractfile(manifest[0]["Config"]).read()
    config = json.loads(config_bytes)
    return {"image_id": inspected["Id"], "config_digest": "sha256:" + hashlib.sha256(config_bytes).hexdigest(),
            "created": config.get("created"), "diff_ids": config["rootfs"]["diff_ids"]}


def binary_hashes(image, platform):
    output = run(["docker", "run", "--rm", "--network", "none", "--platform", platform, image,
                  "python3", "-c", BINARY_HASHES]).stdout
    return json.loads(output.strip().splitlines()[-1])


def rootfs_manifest(image, platform):
    container = run(["docker", "create", "--platform", platform, image]).stdout.strip()
    try:
        with tempfile.TemporaryDirectory(prefix="oiio-rootfs-") as temporary:
            archive_path = pathlib.Path(temporary) / "rootfs.tar"
            run(["docker", "export", "--output", str(archive_path), container])
            manifest = {}
            with tarfile.open(archive_path, mode="r:") as archive:
                for member in archive:
                    name = member.name[2:] if member.name.startswith("./") else member.name
                    name = name.lstrip("/")
                    # docker export changes /etc's mtime when it mounts hosts, hostname, and resolv.conf.
                    if name == "etc" or any(name == prefix or name.startswith(prefix + "/")
                                            for prefix in CONTAINER_RUNTIME_PATHS):
                        continue
                    entry = {"mode": member.mode & 0o7777, "mtime": member.mtime, "uid": member.uid, "gid": member.gid}
                    if member.isfile():
                        digest = hashlib.sha256()
                        source = archive.extractfile(member)
                        for block in iter(lambda: source.read(1 << 20), b""):
                            digest.update(block)
                        entry.update(type="file", sha256=digest.hexdigest())
                    elif member.issym():
                        entry.update(type="symlink", target=member.linkname)
                    elif member.islnk():
                        entry.update(type="hardlink", target=member.linkname)
                    elif member.isdir():
                        entry.update(type="directory")
                    else:
                        entry.update(type="other")
                    manifest[name] = entry
            return manifest
    finally:
        run(["docker", "rm", container], check=False)


def context_digest(directory):
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(directory).as_posix().encode("utf-8") + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
            digest.update((path.stat().st_mode & 0o7777).to_bytes(2, "big"))
    return digest.hexdigest()


def differences(left, right):
    return [{"path": path, "build_a": left.get(path), "build_b": right.get(path)}
            for path in sorted(set(left) | set(right)) if left.get(path) != right.get(path)]


def build(args, context, tag, log_path):
    command = ["docker", "buildx", "bake", "--builder", args.builder, "--file", str(context / "docker-bake.hcl"),
               "--no-cache", "--pull", "--progress=plain", "--load",
               "--set", "*.platform=" + args.platform, "--set", "%s.context=%s" % (args.year, context),
               "--set", "%s.tags=%s" % (args.year, tag), args.year]
    with open(log_path, "w") as log:
        status = subprocess.run(command, cwd=str(context), stdout=log, stderr=subprocess.STDOUT).returncode
    if status:
        raise RuntimeError("cold build failed with exit code %s; see %s" % (status, log_path))


def record(image, platform):
    identity = image_identity(image)
    identity.update(tag=image, binaries=binary_hashes(image, platform), rootfs=rootfs_manifest(image, platform))
    return identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", required=True, help="platform year, for example cy2026")
    parser.add_argument("--platform", required=True, choices=("linux/amd64", "linux/arm64"))
    parser.add_argument("--builder", default="oiio-pinned")
    parser.add_argument("--work-dir", required=True, type=pathlib.Path, help="new directory for contexts and logs")
    parser.add_argument("--baseline-image", help="use an earlier cold build of the same inputs as build A")
    parser.add_argument("--metadata", type=pathlib.Path, help="write the report as JSON to this path")
    parser.add_argument("--keep-images", action="store_true")
    args = parser.parse_args()

    arch = args.platform.split("/")[1]
    tags = []
    try:
        args.work_dir.mkdir(parents=True)
        contexts = [args.work_dir / "build-a", args.work_dir / "build-b"]
        for context in contexts:
            shutil.copytree(str(ROOT), str(context), ignore=IGNORED)
        digests = [context_digest(context) for context in contexts]
        if digests[0] != digests[1]:
            raise RuntimeError("isolated build contexts differ: %s" % digests)

        records = []
        if args.baseline_image:
            records.append(record(args.baseline_image, args.platform))
        for label, context in zip("ab", contexts):
            if len(records) == 2:
                break
            if args.baseline_image and label == "a":
                continue
            tag = "oiio-repro:%s-%s-%s" % (args.year, arch, label)
            tags.append(tag)
            print("cold build %s of %s %s" % (label, args.year, args.platform), flush=True)
            build(args, context, tag, args.work_dir / ("build-%s.log" % label))
            records.append(record(tag, args.platform))

        a, b = records
        report = {
            "schema_version": 1,
            "year": args.year,
            "platform": args.platform,
            "builder": args.builder,
            "source_date_epoch": 0,
            "context_sha256": digests[0],
            "shipped_binaries": len(a["binaries"]),
            "shipped_binaries_equal": a["binaries"] == b["binaries"],
            "binary_differences": differences(a["binaries"], b["binaries"]),
            "rootfs_entries": len(a["rootfs"]),
            "rootfs_content_and_metadata_equal": a["rootfs"] == b["rootfs"],
            "rootfs_differences": differences(a["rootfs"], b["rootfs"]),
            "layer_diff_ids_equal": a["diff_ids"] == b["diff_ids"],
            "config_digest_equal": a["config_digest"] == b["config_digest"],
            "image_id_equal": a["image_id"] == b["image_id"],
            "builds": [{key: value for key, value in item.items() if key not in ("binaries", "rootfs")}
                       for item in records],
            "baseline_image_reused": args.baseline_image,
        }
        if args.metadata:
            args.metadata.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("%s %s: %d shipped binaries %s; %d rootfs entries %s (%d differ); layers %s; config digest %s; image ID %s"
              % (args.year, args.platform, report["shipped_binaries"],
                 "match" if report["shipped_binaries_equal"] else "DIFFER (%d)" % len(report["binary_differences"]),
                 report["rootfs_entries"], "match" if report["rootfs_content_and_metadata_equal"] else "DIFFER",
                 len(report["rootfs_differences"]), "match" if report["layer_diff_ids_equal"] else "differ",
                 "matches" if report["config_digest_equal"] else "differs",
                 "matches" if report["image_id_equal"] else "differs"))
        return 0 if report["shipped_binaries_equal"] and report["rootfs_content_and_metadata_equal"] else 1
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, KeyError) as error:
        print("reproducibility check failed: %s" % error, file=sys.stderr)
        return 1
    finally:
        if not args.keep_images:
            for tag in tags:
                run(["docker", "image", "rm", tag], check=False)


if __name__ == "__main__":
    sys.exit(main())
