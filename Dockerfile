#Download base image centos 7
FROM centos:centos7

ENV PATH="/root/bin:${PATH}"

# Update software repository
# Install dependencies
# Make source directory
RUN	yum -y update && yum clean all && \
	yum -y install autoconf automake bzip2 wget libtiff openexr boost clang freetype-devel gcc gcc-c++ git libtool make pkgconfig zlib-devel
	yum -y install centos-release-scl
	yum -y install devtoolset-6
	yum -y install xorg-x11-util-macros

# Make source directory
RUN mkdir ~/source

# Install gcc
RUN scl enable devtoolset-6 'bash'

# Install cmake
RUN cd ~/source && \
	wget https://cmake.org/files/v3.12/cmake-3.12.3.tar.gz && \
	tar -zxvf cmake-3.12.3.tar.gz && \
	cd cmake-3.12.3 && \
	./bootstrap --prefix=/usr/local && \
	make && \
	make install

# Install zlib
RUN cd ~/source && \
	wget https://www.zlib.net/zlib-1.2.11.tar.gz && \
	tar -zxvf zlib-1.2.11.tar.gz && \
	cd zlib-1.2.11 && \
	./configure && \
	make && \
	make install

# Install IJG (independent jpeg)
RUN cd ~/source && \
	wget http://www.ijg.org/files/jpegsrc.v9c.tar.gz && \
	tar -zxvf jpegsrc.v9c.tar.gz && \
	./configure && \
	make && \
	make install

# Install libpng
RUN cd ~/source && \
	wget http://prdownloads.sourceforge.net/libpng/libpng-1.6.35.tar.gz && \
	tar -zxvf libpng-1.6.35.tar.gz && \
	cd libpng-1.6.35 && \
	./configure && \
	make && \
	make install

# Install openexr
RUN cd ~/source && \
	git clone https://github.com/openexr/openexr.git && \
	cd openexr && \
	cmake . && \
	make && \
	make install

# Install libtiff
RUN cd ~/source && \
	wget http://download.osgeo.org/libtiff/tiff-4.0.9.tar.gz && \
	tar -zxvf tiff-4.0.9.tar.gz && \
	cd tiff-4.0.9 && \


# Install oiio
RUN cd ~/source && \
	git clone git://github.com/OpenImageIO/oiio.git oiio && \
	cd oiio && \
	make && \
	


# # Install NASM
# RUN cd ~/ffmpeg_sources && \
# 	curl -O -L http://www.nasm.us/pub/nasm/releasebuilds/2.13.02/nasm-2.13.02.tar.bz2 && \
# 	tar xjvf nasm-2.13.02.tar.bz2 && \
# 	cd nasm-2.13.02 && \
# 	./autogen.sh && \
# 	./configure --prefix="$HOME/ffmpeg_build" --bindir="$HOME/bin" && \
# 	make && \
# 	make install && \
# 	cd ../ && \
# 	rm -r nasm* && \
# 	yum erase nasm && hash -r

# Make source directory
# Install dependency

# Install oiio


# # Remove source directory and clean yum
# RUN	rm -r ~/ffmpeg_sources && \
# 	yum -y remove cmake gcc gcc-c++ git make mercurial hg && \
# 	yum -y clean all && \
# 	rm -rf /var/cache/yum