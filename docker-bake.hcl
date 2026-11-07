// Build one image per VFX Reference Platform year, for example:
//   docker buildx bake --set '*.platform=linux/arm64' cy2026
// Versions and checksums live in build/locks/cy<year>.json.

group "default" {
  targets = ["cy2026"]
}

target "cy2025" {
  dockerfile = "Dockerfile"
  target     = "runtime-image"
  args = {
    PLATFORM_YEAR      = "cy2025"
    BUILDER_IMAGE      = "rockylinux/rockylinux:8.10@sha256:e8a49c5403b687db05d4d67333fa45808fbe74f36e683cec7abb1f7d0f2338c6"
    RUNTIME_IMAGE      = "rockylinux/rockylinux:8.10-minimal@sha256:6d2ede107b4f005a638728711dae05d5fbbfd8abd521cecf5ab61196b361c965"
    GCC_TOOLSET        = "11"
    AMD64_MARCH        = "x86-64"
    CXX_STANDARD       = "17"
    PYTHON_MAJOR_MINOR = "3.11"
  }
  tags      = ["algernon_vfx/oiio:cy2025"]
  platforms = ["linux/amd64", "linux/arm64"]
}

target "cy2026" {
  dockerfile = "Dockerfile"
  target     = "runtime-image"
  args = {
    PLATFORM_YEAR      = "cy2026"
    BUILDER_IMAGE      = "rockylinux/rockylinux:8.10@sha256:e8a49c5403b687db05d4d67333fa45808fbe74f36e683cec7abb1f7d0f2338c6"
    RUNTIME_IMAGE      = "rockylinux/rockylinux:8.10-minimal@sha256:6d2ede107b4f005a638728711dae05d5fbbfd8abd521cecf5ab61196b361c965"
    GCC_TOOLSET        = "14"
    AMD64_MARCH        = "x86-64"
    CXX_STANDARD       = "20"
    PYTHON_MAJOR_MINOR = "3.13"
  }
  tags      = ["algernon_vfx/oiio:cy2026", "algernon_vfx/oiio:latest"]
  platforms = ["linux/amd64", "linux/arm64"]
}

target "cy2027" {
  dockerfile = "Dockerfile"
  target     = "runtime-image"
  args = {
    PLATFORM_YEAR      = "cy2027"
    BUILDER_IMAGE      = "rockylinux/rockylinux:9.8@sha256:8101994123cf3d0a8fee517bee7f39e555c7d92bd2d9eb3303cc988a0eeed00f"
    RUNTIME_IMAGE      = "rockylinux/rockylinux:9.8-minimal@sha256:e1d0a9f5ed99d52e7faf03afe7ee32e48b231c4dd9586808b3d1aedf894dff04"
    GCC_TOOLSET        = "14"
    AMD64_MARCH        = "x86-64-v2"
    CXX_STANDARD       = "20"
    PYTHON_MAJOR_MINOR = "3.13"
  }
  tags      = ["algernon_vfx/oiio:cy2027"]
  platforms = ["linux/amd64", "linux/arm64"]
}
