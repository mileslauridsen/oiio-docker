#Download base image centos 7
FROM centos:centos7

ENV PATH="/root/bin:${PATH}"

# Update software repository
# Install dependencies
# Make source directory
RUN	yum -y clean all && \
	yum -y install centos-release-scl && \
	yum -y install devtoolset-6 devtoolset-6-gcc-c++ llvm-toolset-7-clang-devel devtoolset-6-make && \
	source scl_source enable devtoolset-6 && \
	scl enable devtoolset-6 bash && \
	yum -y install autoconf automake bzip2 boost-devel boost-build boost-python numpy \
	wget python-devel libpng-devel freetype-devel git libtool python27-numpy \
	libtiff pkgconfig jasper libjpeg8 libjpeg-turbo-devel giflib-devel bzip2-devel libwebp-devel \
	PyOpenGL mesa-libGLw freeglut-devel jasper-devel glew-devel xorg-x11-util-macros && \
	yum -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm && \
	yum -y install OpenColorIO OpenColorIO-tools OpenImageIO-utils python-OpenImageIO

# # Install cmake
# # Make source directory
# RUN mkdir ~/source && \
# 	cd ~/source && \
# 	wget https://cmake.org/files/v3.12/cmake-3.12.3.tar.gz && \
# 	tar -zxvf cmake-3.12.3.tar.gz && \
# 	cd cmake-3.12.3 && \
# 	source scl_source enable devtoolset-6 && \
# 	scl enable devtoolset-6 bash && \
# 	./bootstrap --prefix=/usr/local && \
# 	make && \
# 	make install

# # Install zlib
# RUN cd ~/source && \
# 	wget https://www.zlib.net/zlib-1.2.11.tar.gz && \
# 	tar -zxvf zlib-1.2.11.tar.gz && \
# 	cd zlib-1.2.11 && \
# 	source scl_source enable devtoolset-6 && \
# 	scl enable devtoolset-6 bash && \
# 	./configure --shared --prefix=/usr/local && \
# 	make && \
# 	make install

# # Install IJG (independent jpeg)
# RUN cd ~/source && \
# 	wget http://www.ijg.org/files/jpegsrc.v9c.tar.gz && \
# 	tar -zxvf jpegsrc.v9c.tar.gz && \
# 	cd jpeg-9c && \
# 	source scl_source enable devtoolset-6 && \
# 	scl enable devtoolset-6 bash && \
# 	./configure --prefix=/usr/local && \
# 	make && \
# 	make install

# # # Install libpng
# # RUN cd ~/source && \
# # 	wget http://prdownloads.sourceforge.net/libpng/libpng-1.6.35.tar.gz && \
# # 	tar -zxvf libpng-1.6.35.tar.gz && \
# # 	cd libpng-1.6.35 && \
# # 	./configure --prefix=/usr/local --with-zlib-prefix=/usr/local && \
# # 	make && \
# # 	make install

# # # Install boost
# # RUN cd ~/source && \
# # 	wget https://dl.bintray.com/boostorg/release/1.66.0/source/boost_1_66_0.tar.gz && \
# # 	tar -zxvf boost_1_66_0.tar.gz && \
# # 	cd boost_1_66_0 && \
# # 	python_root="/usr/include/python2.7" && \
# # 	ln -s $python_root/pyconfig-64.h $python_root/pyconfig.h && \
# # 	./bootstrap.sh --prefix=/usr/local --with-python-root=$python_root && \
# # 	./b2 install; exit 0 && \
# # 	ls /usr

# # ENV PYTHON_LIBRARIES="/usr/lib/libpython2.7.so"
# # ENV PYTHON_INCLUDE_DIRS="/usr/include/python2.7"
# # ENV BOOST_ROOT="/usr/local/boost"
# # ENV BOOST_INCLUDEDIR="/usr/local/include"
# # ENV BOOST_LIBRARYDIR="/usr/local/lib"

# # Install libtiff
# RUN cd ~/source && \
# 	wget http://download.osgeo.org/libtiff/tiff-4.0.9.tar.gz && \
# 	tar -zxvf tiff-4.0.9.tar.gz && \
# 	cd tiff-4.0.9 && \
# 	source scl_source enable devtoolset-6 && \
# 	scl enable devtoolset-6 bash && \
# 	./configure --prefix=/usr/local && \
# 	make && \
# 	make install

# # Install lcms
# RUN cd ~/source && \
# 	wget https://downloads.sourceforge.net/project/lcms/lcms/2.9/lcms2-2.9.tar.gz && \
# 	tar -zxvf lcms2-2.9.tar.gz && \
# 	cd lcms2-2.9 && \
# 	source scl_source enable devtoolset-6 && \
# 	scl enable devtoolset-6 bash && \
# 	./configure --prefix=/usr/local && \
# 	make && \
# 	make install

# # Install libraw
# RUN cd ~/source && \
# 	wget https://www.libraw.org/data/LibRaw-0.19.0.tar.gz && \
# 	tar -zxvf LibRaw-0.19.0.tar.gz && \
# 	cd LibRaw-0.19.0 && \
# 	source scl_source enable devtoolset-6 && \
# 	scl enable devtoolset-6 bash && \
# 	./configure --prefix=/usr/local --enable-lcms && \
# 	make && \
# 	make install

# # Install openexr
# RUN cd ~/source && \
# 	git clone https://github.com/openexr/openexr.git && \
# 	cd openexr && \
# 	source scl_source enable devtoolset-6 && \
# 	scl enable devtoolset-6 bash && \
# 	cmake . -DBUILD_TIFF=ON && \
# 	make && \
# 	make install

# # # Install openexr
# # RUN cd ~/source && \
# # 	git clone https://github.com/openexr/openexr.git && \
# # 	cd openexr && \
# # 	cmake . -DBUILD_TIFF=ON \
# # 	-DPYTHON_LIBRARY="/usr/lib/libpython2.7.so" \
# # 	-DPYTHON_INCLUDE_DIR="/usr/include/python2.7/" \
# # 	-DPYTHON_EXECUTABLE="/usr/bin/python" \
# # 	-DBOOST_INCLUDE_DIR="/usr/local/include" \
# # 	-DBOOST_ROOT:PATHNAME="usr/local/boost" \
# # 	-DBOOST_LIBRARY_DIR="/usr/local/lib" && \
# # 	make && \
# # 	make install

# # # Install libtiff
# # RUN cd ~/source && \
# # 	wget http://download.osgeo.org/libtiff/tiff-4.0.9.tar.gz && \
# # 	tar -zxvf tiff-4.0.9.tar.gz && \
# # 	cd tiff-4.0.9 && \
# # 	./configure

# # Install oiio
# RUN cd ~/source && \
# 	git clone git://github.com/OpenImageIO/oiio.git oiio && \
# 	cd oiio && \
# 	mkdir build && \
# 	cd build && \
# 	source scl_source enable devtoolset-6 && \
# 	scl enable devtoolset-6 bash && \
# 	cmake --DCMAKE_INSTALL_PREFIX:PATH=/usr/local .. && \
# 	make -j2 && \
# 	make install

# # # Install OpenColorIO
# # RUN cd ~/source && \
# # 	git clone https://github.com/imageworks/OpenColorIO.git && \
# # 	cd OpenColorIO && \
# # 	git checkout tags/v1.1.0 && \
# # 	source scl_source enable devtoolset-6 && \
# # 	scl enable devtoolset-6 bash && \
# # 	# OCIO_USE_SSE=OFF && \
# # 	cmake --DCMAKE_INSTALL_PREFIX:PATH=/usr/local --OCIO_BUILD_GPU_TESTS=OFF . && \
# # 	# -DUSE_SSE
# # 	make -j2 && \
# # 	make install

# # Install OpenColorIO for tar
# RUN cd ~/source && \
# 	wget https://github.com/imageworks/OpenColorIO/archive/v1.1.0.tar.gz && \
# 	tar -zxvf v1.1.0.tar.gz && \
# 	cd OpenColorIO-1.1.0 && \
# 	source scl_source enable devtoolset-6 && \
# 	scl enable devtoolset-6 bash && \
# 	cmake --DCMAKE_INSTALL_PREFIX:PATH=/usr/local -DUSE_SSE=OFF --OCIO_BUILD_GPU_TESTS=OFF . && \
# 	make -j2 && \
# 	make install

# Alt OpenColorIO install
#RUN yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
#	yum install OpenColorIO
#	

# # # Install NASM
# # RUN cd ~/ffmpeg_sources && \
# # 	curl -O -L http://www.nasm.us/pub/nasm/releasebuilds/2.13.02/nasm-2.13.02.tar.bz2 && \
# # 	tar xjvf nasm-2.13.02.tar.bz2 && \
# # 	cd nasm-2.13.02 && \
# # 	./autogen.sh && \
# # 	./configure --prefix="$HOME/ffmpeg_build" --bindir="$HOME/bin" && \
# # 	make && \
# # 	make install && \
# # 	cd ../ && \
# # 	rm -r nasm* && \
# # 	yum erase nasm && hash -r

# # Make source directory
# # Install dependency

# # Install oiio


# # # Remove source directory and clean yum
# # RUN	rm -r ~/ffmpeg_sources && \
# # 	yum -y remove cmake gcc gcc-c++ git make mercurial hg && \
# # 	yum -y clean all && \
# # 	rm -rf /var/cache/yum