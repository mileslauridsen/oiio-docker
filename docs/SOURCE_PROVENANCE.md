# Source Provenance

Each platform year's lock, `build/locks/cy<year>.json`, is the authoritative list of what that image is built from: every source archive, NumPy wheel, and build tool, with its version, HTTPS URL, SHA-256, and any upstream signature. The Dockerfile names no sources. Its build arguments only select a year's lock.

`build/fetch_sources.py` runs in the Dockerfile's `sources` stage. For each locked input it:

1. downloads over HTTPS only, rejecting a redirect to anything else and failing on HTTP errors;
2. checks the SHA-256;
3. checks every signature the lock records for it;
4. only then extracts it.

Every later build step runs with `--network=none`, so nothing can be fetched after this stage. `scripts/validate_lock.py` checks the locks and shows that a bad checksum or a bad signature stops the helper before extraction.

## How Each Input Is Verified

| Inputs | Verification at build time |
| --- | --- |
| zlib, libjpeg-turbo, libtiff, expat, CPython | SHA-256, then the project's detached GPG signature, which must come from the pinned key fingerprint. |
| Imath, OpenEXR, OpenColorIO, OpenImageIO | SHA-256, then the project's Sigstore bundle, checked offline with the locked `cosign` and the pinned Sigstore trust root against the exact GitHub workflow that signs that tag (`.github/workflows/release-sign.yml@refs/tags/v<version>`, issuer `https://token.actions.githubusercontent.com`). |
| OpenColorIO 2.4.2 (CY2025) | SHA-256 only. This release publishes no signed tarball, so the lock uses GitHub's tag archive. `validate_lock.py` records it as the one allowed exception. |
| NumPy wheels | SHA-256 published by PyPI. |
| `cosign` 3.1.3 | SHA-256 published in the release's `cosign_checksums.txt`, matching a local computation. It is fetched and checked first, used only in the `sources` stage, and never shipped. |
| NASM, libpng, libdeflate, yaml-cpp, pystring, minizip-ng, `sse2neon`, pybind11, fmt, robin-map, nanobind | SHA-256 computed locally from the pinned HTTPS URL. None of these publishes signatures for the locked file. |

A locally computed SHA-256 fixes the exact bytes, so a changed or corrupted download fails. It is not an independent statement from the publisher, the way a signature or a publisher checksum is.

The ASWF projects' signed release tarballs replaced the GitHub tag archives on 2026-11-02. For every year, the release tarball unpacked to exactly the same files as the tag archive the images had been built and verified from.

## Pinned GPG Keys

The keys are in `build/keys/`. Each was fetched from keys.openpgp.org, where the user ID's email address is verified, and is pinned by its primary-key fingerprint. gpgv reports the primary fingerprint for a signature made by any of the key's subkeys.

| Key file | Signer | Fingerprint | Signs |
| --- | --- | --- | --- |
| `zlib-mark-adler.asc` | Mark Adler | `5ED46A6721D365587791E2AA783FCD8E58BCAFBA` | zlib 1.3.1, 1.3.2 |
| `libjpeg-turbo.asc` | The libjpeg-turbo Project | `0338C8D8D9FDA62CF9C421BD7EC2DBB6F4DBF434` | libjpeg-turbo 3.1.2 |
| `libtiff-even-rouault.asc` | Even Rouault | `B1FA7D81EEB8E66399178B9733EBBFC47B3DD87D` | libtiff 4.7.1 |
| `expat-sebastian-pipping.asc` | Sebastian Pipping | `3176EF7DB2367F1FCA4F306B1F9B0E909AF37285` | expat 2.7.2, 2.8.5 |
| `cpython-pablo-galindo-salgado.asc` | Pablo Galindo Salgado | `A035C8C19219BA821ECEA86B64E628F8D684696D` | CPython 3.11.18 |
| `cpython-thomas-wouters.asc` | Thomas Wouters | `7169605F62C751356D054A26A821E680E5FA6305` | CPython 3.13.18 |

Cross-checks:

- libjpeg-turbo's fingerprint matches the one libjpeg-turbo.org publishes.
- python.org lists Pablo Galindo Salgado as the 3.11 release manager (key ID `64E628F8D684696D`) and Thomas Wouters as the 3.13 release manager (key ID `A821E680E5FA6305`). CPython 3.11.18 is signed by `FFE87404168BD847`, the signing subkey of Pablo Galindo Salgado's key.
- zlib, libtiff, and expat do not publish a fingerprint on their project pages that this check found. Their keys rest on keys.openpgp.org's verified addresses for the named maintainers.

## Pinned Sigstore Trust Root

`build/keys/sigstore-trusted-root.json` holds the public Sigstore instance's trust root: the Fulcio certificate authorities, the Rekor transparency-log keys, the certificate-transparency log keys, and the timestamp authority, each with the period it is valid for. Every Sigstore entry in the locks names this file and pins its SHA-256 (`6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66`). The helper checks that hash before it runs `cosign verify-blob --trusted-root`.

With the trust root pinned, Sigstore verification needs no network. Each bundle already carries the signing certificate, the signature, and the Rekor entry with its inclusion proof, so neither Fulcio nor Rekor is contacted. Without the pinned root, `cosign` fetches the trust root from `https://tuf-repo-cdn.sigstore.dev` on every run and fails when that host cannot be reached.

The file was fetched on 2026-11-03 by the locked `cosign`, whose TUF client checked it against Sigstore's signed TUF metadata (root version 16, targets version 14). Its SHA-256 matches the hash in that `targets.json` and the copy in the [sigstore/root-signing](https://github.com/sigstore/root-signing) repository.

## Shipped Licenses

Each lock entry's `shipped` flag records whether its code reaches the image. Everything is shipped except NASM and `cosign`, which only build or verify, and `validate_lock.py` enforces that. Shipped includes the static libraries linked into OCIO (expat, yaml-cpp, pystring, minizip-ng), the header-only and compiled-in code (`sse2neon`, pybind11, fmt, robin-map, nanobind), and CY2025's libdeflate, which is compiled into OpenEXR.

`scripts/collect_licenses.py` runs in the compile stage, after OIIO is installed. For each shipped source it copies the `COPYING`, `LICENSE`, `COPYRIGHT`, `NOTICE`, `PATENTS`, and `THIRD-PARTY` files from the source tree to three directory levels deep, so bundled code's notices come too: OpenEXR's vendored libdeflate, OpenJPH, and zstd, and CPython's bundled expat and hash implementations. Tests, examples, `contrib/`, documentation copies, and other platforms' packaging are skipped, because they are not built. Two notices have other names and are added by name: libjpeg-turbo's `README.ijg`, which holds the IJG terms, and CPython's `Doc/license.rst`, which lists the third-party code CPython incorporates. For NumPy it copies the license files from the installed wheel's `dist-info`, which cover the OpenBLAS and gfortran libraries the wheel bundles. The collector fails if any shipped component yields no notice.

The image holds them in `/opt/vfx/share/licenses/<component>/`, with `components.json` listing each component's version and each file's SHA-256: 28 files for 18 components in CY2026, 30 for 19 in CY2025, and 46 for 19 in CY2027, whose NumPy wheel alone has 17. They add 0.4–0.6 MB to an image. `scripts/validate_image.py` checks that the manifest names exactly the lock's shipped components and versions, and that every file is present with its recorded hash. The Rocky base image's own packages keep their license files in `/usr/share/licenses`; the validator checks that `glibc` and `libgcc` are there. Rocky's `libstdc++` package carries no separate license file; its terms are GCC's, which `libgcc` carries.

This collects the notices; it is not a legal review of the licenses.

## Known Limits

- **Trust root rotation.** Sigstore adds keys to its trust root when it rotates a certificate authority or log. The current keys have open-ended validity, so the pinned file keeps verifying the locked bundles. A future release signed with a key added after 2026-11-03 will fail to verify until the file is refreshed.
- **Key expiry.** Sebastian Pipping's signing subkey expires on 2026-12-28. gpgv still accepts signatures made before a key expired, but check the expat signature after that date, and refresh the key file if the maintainer extends it.
- **Trust in `cosign`.** It is trusted through its publisher checksum, fetched over HTTPS from GitHub. Its own Sigstore signature is not checked, since that would need a verifier trusted some other way.

## Lock Update Procedure

1. Change the entry in each affected lock: version, HTTPS URL, archive name, source root, SHA-256, checksum provenance, and for a new input whether it is `shipped`. For a signed release, also update the signature URL and file. For GPG, review the signer and the pinned key fingerprint; for Sigstore, update the tag in the workflow identity.
2. For a new GPG signer, fetch the key from keys.openpgp.org or the project, confirm its fingerprint against what the project publishes, and add it to `build/keys/`.
   If a new Sigstore bundle fails to verify against the pinned trust root, refresh it: run the locked `cosign verify-blob` once with network access and a new, empty `HOME`, then take `$HOME/.sigstore/root/tuf-repo-cdn.sigstore.dev/targets/trusted_root.json`, which cosign's TUF client has checked. Confirm its SHA-256 matches the `trusted_root.json` hash in the `targets.json` beside it and the copy in sigstore/root-signing. Replace `build/keys/sigstore-trusted-root.json`, and update `trusted_root_sha256` in every lock.
3. Run `python3 scripts/validate_lock.py`.
4. Fetch and verify the year's inputs on both architectures, without building the rest:

   ```sh
   docker buildx bake --set '*.platform=linux/arm64' --set 'cy2026.target=sources' --set 'cy2026.output=type=cacheonly' --progress=plain cy2026
   ```

   Repeat with `linux/amd64`. The log shows each `SHA-256 verified`, `GPG signature verified`, and `Sigstore signature verified` line. A trusted-root SHA-256 mismatch stops the fetch before `cosign` runs.
5. Build every affected year on both architectures, run `scripts/validate_image.py` (which also checks the shipped license files) and `scripts/smoke_images.py`, and record the results in this document and the [implementation log](IMPLEMENTATION.md).
