#Download base image centos 7
FROM centos:centos7

# Install all via yum
RUN	yum -y clean all && \
	yum -y install centos-release-scl && \
	yum -y install devtoolset-6 devtoolset-6-gcc-c++ llvm-toolset-7-clang-devel devtoolset-6-make && \
	yum -y install autoconf automake bzip2 boost-devel boost-build boost-python numpy \
	wget python-devel libpng-devel freetype-devel git libtool python27-numpy \
	libtiff pkgconfig jasper libjpeg8 libjpeg-turbo-devel giflib-devel bzip2-devel libwebp-devel \
	PyOpenGL mesa-libGLw freeglut-devel jasper-devel glew-devel xorg-x11-util-macros && \
	yum -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm && \
	yum -y install OpenColorIO OpenColorIO-tools OpenImageIO-utils python-OpenImageIO