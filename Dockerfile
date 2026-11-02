# syntax=docker/dockerfile:1.7.1@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

# Defaults build the current VFX Reference Platform year. docker-bake.hcl sets
# these per year from build/locks/cy<year>.json.
ARG PLATFORM_YEAR=cy2026
ARG BUILDER_IMAGE=rockylinux/rockylinux:8.10@sha256:e8a49c5403b687db05d4d67333fa45808fbe74f36e683cec7abb1f7d0f2338c6
ARG RUNTIME_IMAGE=rockylinux/rockylinux:8.10-minimal@sha256:6d2ede107b4f005a638728711dae05d5fbbfd8abd521cecf5ab61196b361c965
ARG GCC_TOOLSET=14
ARG CXX_STANDARD=20
ARG PYTHON_MAJOR_MINOR=3.13
ARG BUILD_JOBS=8

FROM ${BUILDER_IMAGE} AS builder

ARG GCC_TOOLSET
ARG TARGETARCH
ENV LC_ALL=C LANG=C TZ=UTC

RUN set -eu; \
    test "$TARGETARCH" = amd64 -o "$TARGETARCH" = arm64; \
    dnf -y install \
        gcc-toolset-${GCC_TOOLSET}-gcc-c++ cmake make patch tar xz findutils pkgconf-pkg-config \
        bzip2-devel xz-devel libffi-devel openssl-devel; \
    dnf clean all

# Compile generic x86-64-v1 or ARMv8-A code with the platform's gcc-toolset compiler.
RUN set -eu; \
    case "$TARGETARCH" in \
        amd64) CPU_FLAGS='-march=x86-64 -mtune=generic' ;; \
        arm64) CPU_FLAGS='-march=armv8-a -mtune=generic' ;; \
    esac; \
    TOOLSET=/opt/rh/gcc-toolset-${GCC_TOOLSET}/root/usr/bin; \
    printf '#!/bin/sh\nexec %s/gcc %s "$@"\n' "$TOOLSET" "$CPU_FLAGS" > /usr/local/bin/vfx-gcc; \
    printf '#!/bin/sh\nexec %s/g++ %s "$@"\n' "$TOOLSET" "$CPU_FLAGS" > /usr/local/bin/vfx-g++; \
    chmod 755 /usr/local/bin/vfx-gcc /usr/local/bin/vfx-g++
ENV PATH=/opt/rh/gcc-toolset-${GCC_TOOLSET}/root/usr/bin:/opt/vfx/bin:/opt/build-tools/bin:${PATH}
ENV CC=/usr/local/bin/vfx-gcc CXX=/usr/local/bin/vfx-g++
ENV PKG_CONFIG_PATH=/opt/vfx/lib/pkgconfig:/opt/deps/lib/pkgconfig

# Fetch only locked inputs; the helper verifies every SHA-256 before extracting.
FROM builder AS sources
ARG PLATFORM_YEAR
ARG TARGETPLATFORM
COPY build/fetch_sources.py build/locks/${PLATFORM_YEAR}.json /build/
RUN PY=$(command -v python3 || echo /usr/libexec/platform-python); \
    "$PY" -u /build/fetch_sources.py --lockfile /build/${PLATFORM_YEAR}.json \
        --platform "$TARGETPLATFORM" --all --output-dir /src/downloads --extract-dir /src

# Every compile step runs without network access. /opt/vfx ships; /opt/deps and
# /opt/build-tools hold build-only static libraries, headers, and tools.
FROM builder AS compile
ARG CXX_STANDARD
ARG PYTHON_MAJOR_MINOR
ARG BUILD_JOBS
COPY --from=sources /src /src
# Link-time optimization stays off everywhere: pybind11 would otherwise enable it for the Python
# modules, and gcc-toolset-14's lto1 hit an internal compiler error linking OIIO's module on amd64.
RUN printf '#!/bin/sh\nexec cmake -G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_PREFIX_PATH="/opt/vfx;/opt/deps" -DCMAKE_INSTALL_RPATH=/opt/vfx/lib -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF -DCMAKE_CXX_STANDARD=%s "$@"\n' "$CXX_STANDARD" > /usr/local/bin/vfx-cmake && \
    chmod 755 /usr/local/bin/vfx-cmake

# Install NASM
RUN --network=none cd /src/nasm && \
    ./configure --prefix=/opt/build-tools && \
    make -j${BUILD_JOBS} && \
    make install

# Install zlib
RUN --network=none cd /src/zlib && \
    ./configure --prefix=/opt/vfx && \
    make -j${BUILD_JOBS} && \
    make install

# Install libjpeg-turbo
RUN --network=none cd /src/libjpeg-turbo && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/vfx -DENABLE_STATIC=OFF \
        -DCMAKE_ASM_NASM_COMPILER=/opt/build-tools/bin/nasm && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build

# Install libpng
RUN --network=none cd /src/libpng && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/vfx -DPNG_STATIC=OFF -DPNG_TESTS=OFF -DPNG_TOOLS=OFF \
        -DZLIB_ROOT=/opt/vfx && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build

# Install libtiff
RUN --network=none cd /src/libtiff && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/vfx -Dtiff-tools=OFF -Dtiff-tests=OFF -Dtiff-contrib=OFF \
        -Dtiff-docs=OFF -Dtiff-cxx=OFF -Dtiff-opengl=OFF -Dzlib=ON -Djpeg=ON -Dlzma=OFF -Dzstd=OFF -Dwebp=OFF -Djbig=OFF -Dlerc=OFF \
        -Dlibdeflate=OFF -Djpeg12=OFF -DZLIB_ROOT=/opt/vfx -DJPEG_ROOT=/opt/vfx && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build

# Install CPython
RUN --network=none cd /src/cpython && \
    ./configure --prefix=/opt/vfx --enable-shared --with-ensurepip=no --without-static-libpython \
        CPPFLAGS="-I/opt/vfx/include" LDFLAGS="-L/opt/vfx/lib -Wl,-rpath,/opt/vfx/lib" && \
    make -j${BUILD_JOBS} && \
    make install && \
    python3 -c "import ssl, zlib, ctypes, bz2, lzma; print('python modules ok')"

# Install NumPy from the locked wheel, using CPython's bundled pip only for the install
RUN --network=none python3 -m ensurepip && \
    python3 -m pip install --no-index --no-deps /src/downloads/numpy-*.whl && \
    python3 -m pip uninstall -y pip && \
    python3 -c "import numpy; print('numpy', numpy.__version__)"

# Install Imath
RUN --network=none cd /src/imath && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/vfx -DBUILD_TESTING=OFF -DPYTHON=OFF && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build

# Install OpenEXR with its vendored libdeflate, OpenJPH, and (3.5 and later) zstd
RUN --network=none cd /src/openexr && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/vfx -DBUILD_TESTING=OFF -DOPENEXR_BUILD_TOOLS=OFF \
        -DOPENEXR_BUILD_EXAMPLES=OFF -DOPENEXR_FORCE_INTERNAL_DEFLATE=ON -DOPENEXR_FORCE_INTERNAL_OPENJPH=ON \
        -DOPENEXR_FORCE_INTERNAL_ZSTD=ON && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build

# Install expat (static, for OCIO)
RUN --network=none cd /src/expat && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/deps -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
        -DEXPAT_SHARED_LIBS=OFF -DEXPAT_BUILD_TOOLS=OFF -DEXPAT_BUILD_EXAMPLES=OFF -DEXPAT_BUILD_TESTS=OFF \
        -DEXPAT_BUILD_DOCS=OFF && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build

# Install yaml-cpp (static, for OCIO)
RUN --network=none cd /src/yaml-cpp && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/deps -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
        -DYAML_BUILD_SHARED_LIBS=OFF -DYAML_CPP_BUILD_TESTS=OFF -DYAML_CPP_BUILD_TOOLS=OFF \
        -DYAML_CPP_BUILD_CONTRIB=OFF -DYAML_CPP_FORMAT_SOURCE=OFF && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build

# Install pystring (static, for OCIO); its CMake project builds only a shared library without headers
RUN --network=none cd /src/pystring && \
    "$CXX" -std=c++${CXX_STANDARD} -O2 -fPIC -c pystring.cpp -o pystring.o && \
    mkdir -p /opt/deps/lib /opt/deps/include/pystring && \
    ar rcs /opt/deps/lib/libpystring.a pystring.o && \
    cp pystring.h /opt/deps/include/pystring/

# Install minizip-ng (static, zlib only, for OCIO)
RUN --network=none cd /src/minizip-ng && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/deps -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
        -DBUILD_SHARED_LIBS=OFF -DMZ_COMPAT=OFF -DMZ_ZLIB=ON -DMZ_BZIP2=OFF -DMZ_LZMA=OFF -DMZ_PPMD=OFF -DMZ_ZSTD=OFF \
        -DMZ_LIBCOMP=OFF -DMZ_OPENSSL=OFF -DMZ_LIBBSD=OFF -DMZ_ICONV=OFF -DMZ_PKCRYPT=OFF -DMZ_WZAES=OFF \
        -DMZ_FETCH_LIBS=OFF -DZLIB_ROOT=/opt/vfx && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build

# Install sse2neon and pybind11 headers
RUN --network=none mkdir -p /opt/deps/include/sse2neon && \
    cp /src/sse2neon/sse2neon.h /opt/deps/include/sse2neon/ && \
    cd /src/pybind11 && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/deps -DPYBIND11_TEST=OFF -DPython_EXECUTABLE=/opt/vfx/bin/python3 && \
    cmake --install build

# Install OpenColorIO
RUN --network=none cd /src/opencolorio && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/vfx -DOCIO_INSTALL_EXT_PACKAGES=NONE \
        -DOCIO_BUILD_APPS=OFF -DOCIO_BUILD_TESTS=OFF -DOCIO_BUILD_GPU_TESTS=OFF -DOCIO_BUILD_DOCS=OFF \
        -DOCIO_BUILD_OPENFX=OFF -DOCIO_BUILD_PYTHON=ON -DOCIO_PYTHON_VERSION=${PYTHON_MAJOR_MINOR} \
        -DPython_EXECUTABLE=/opt/vfx/bin/python3 -Dexpat_ROOT=/opt/deps -Dexpat_STATIC_LIBRARY=ON \
        -Dyaml-cpp_ROOT=/opt/deps -Dyaml-cpp_STATIC_LIBRARY=ON -Dpystring_ROOT=/opt/deps \
        -Dminizip-ng_ROOT=/opt/deps -Dminizip-ng_STATIC_LIBRARY=ON -Dsse2neon_ROOT=/opt/deps/include \
        -Dpybind11_ROOT=/opt/deps -DImath_ROOT=/opt/vfx -DZLIB_ROOT=/opt/vfx && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build

# Install fmt and robin-map headers
RUN --network=none cd /src/fmt && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/deps -DFMT_TEST=OFF -DFMT_DOC=OFF -DFMT_INSTALL=ON && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build && \
    cd /src/robin-map && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/deps && \
    cmake --install build

# Install nanobind for OIIO 3.2 and later, using the locked robin-map instead of its git submodule
RUN --network=none if [ -d /src/nanobind ]; then \
        cd /src/nanobind && \
        vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/deps -DNB_TEST=OFF -DNB_CREATE_INSTALL_RULES=ON \
            -DNB_USE_SUBMODULE_DEPS=OFF -DPython_EXECUTABLE=/opt/vfx/bin/python3 && \
        cmake --install build; \
    fi

# Install OpenImageIO with only the tools, Python bindings, and image-format plugins in scope.
# OIIO 3.2 and later build nanobind bindings; earlier releases use pybind11.
RUN --network=none set -eu; \
    BINDINGS=""; \
    if [ -d /opt/deps/nanobind ]; then \
        BINDINGS="-DOIIO_PYTHON_BINDINGS_BACKEND=nanobind -Dnanobind_DIR=/opt/deps/nanobind/cmake"; \
    fi; \
    cd /src/openimageio && \
    vfx-cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/opt/vfx -DOIIO_BUILD_TESTS=OFF -DOIIO_BUILD_TOOLS=ON $BINDINGS \
        -DBUILD_DOCS=OFF -DINSTALL_DOCS=OFF -DINSTALL_FONTS=OFF -DOIIO_DOWNLOAD_MISSING_TESTDATA=OFF \
        -DUSE_PYTHON=ON -DPYTHON_VERSION=${PYTHON_MAJOR_MINOR} -DPython_EXECUTABLE=/opt/vfx/bin/python3 \
        -DENABLE_Freetype=OFF -DENABLE_OpenCV=OFF -DENABLE_TBB=OFF -DENABLE_DCMTK=OFF -DENABLE_FFmpeg=OFF \
        -DENABLE_GIF=OFF -DENABLE_Libheif=OFF -DENABLE_LibRaw=OFF -DENABLE_OpenJPEG=OFF -DENABLE_openjph=OFF \
        -DENABLE_OpenVDB=OFF -DENABLE_Ptex=OFF -DENABLE_WebP=OFF -DENABLE_JXL=OFF -DENABLE_libuhdr=OFF \
        -DENABLE_libdeflate=OFF -DENABLE_zstd=OFF -DENABLE_Nuke=OFF -DENABLE_BZip2=OFF -DENABLE_OpenGL=OFF -DENABLE_Qt5=OFF \
        -DENABLE_Qt6=OFF -DUSE_QT=OFF -DUSE_R3DSDK=OFF && \
    cmake --build build -j${BUILD_JOBS} && \
    cmake --install build

# Keep only runtime files in /opt/vfx, drop -O/-OO bytecode, then strip shipped ELF files outside the NumPy wheel.
RUN --network=none set -eu -o pipefail; \
    cd /opt/vfx; \
    rm -rf include share/man share/doc lib/pkgconfig lib/cmake lib/*.a; \
    rm -rf lib/python${PYTHON_MAJOR_MINOR}/test lib/python${PYTHON_MAJOR_MINOR}/idlelib \
        lib/python${PYTHON_MAJOR_MINOR}/tkinter lib/python${PYTHON_MAJOR_MINOR}/turtledemo \
        lib/python${PYTHON_MAJOR_MINOR}/ensurepip bin/idle3* bin/pydoc3* bin/python*-config; \
    find /opt/vfx -name '*.opt-[12].pyc' -delete; \
    stripped=0; \
    for f in $(find /opt/vfx -type f -not -path '*/site-packages/numpy*'); do \
        if [ "$(head -c 4 "$f" | od -An -tx1 | tr -d ' ')" = 7f454c46 ]; then \
            strip --strip-unneeded "$f"; stripped=$((stripped + 1)); \
        fi; \
    done; \
    echo "stripped $stripped ELF files"; \
    test "$stripped" -gt 50

FROM ${RUNTIME_IMAGE} AS runtime-image

COPY --from=compile /opt/vfx /opt/vfx

ENV PATH=/opt/vfx/bin:$PATH LANG=C.UTF-8

# The minimal base has no useradd, so create the non-root user directly.
RUN echo 'algernon:x:1000:1000::/home/algernon:/bin/bash' >> /etc/passwd && \
    echo 'algernon:x:1000:' >> /etc/group && \
    mkdir -p /home/algernon && \
    chown 1000:1000 /home/algernon
USER algernon
ENV HOME=/home/algernon
WORKDIR /home/algernon
