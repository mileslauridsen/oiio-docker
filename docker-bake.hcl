// Build one image per VFX Reference Platform year, for example:
//   docker buildx bake --set '*.platform=linux/arm64' cy2026
// Versions and checksums live in build/locks/cy<year>.json.

group "default" {
  targets = ["cy2026"]
}

target "cy2026" {
  dockerfile = "Dockerfile"
  target     = "runtime-image"
  args = {
    PLATFORM_YEAR      = "cy2026"
    BUILDER_IMAGE      = "rockylinux/rockylinux:8.10@sha256:e8a49c5403b687db05d4d67333fa45808fbe74f36e683cec7abb1f7d0f2338c6"
    RUNTIME_IMAGE      = "rockylinux/rockylinux:8.10-minimal@sha256:6d2ede107b4f005a638728711dae05d5fbbfd8abd521cecf5ab61196b361c965"
    GCC_TOOLSET        = "14"
    CXX_STANDARD       = "20"
    PYTHON_MAJOR_MINOR = "3.13"
  }
  tags      = ["algernon_vfx/oiio:cy2026", "algernon_vfx/oiio:latest"]
  platforms = ["linux/amd64", "linux/arm64"]
}
