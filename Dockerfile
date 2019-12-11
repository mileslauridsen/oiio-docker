#Download base image centos 7
FROM centos:centos7 AS compile-image

# Install all via yum
RUN yum -y update
RUN	yum -y clean all && \
	yum -y install centos-release-scl && \
	yum -y install devtoolset-6 devtoolset-6-gcc-c++ llvm-toolset-7-clang-devel devtoolset-6-make

RUN yum -y install autoconf automake bzip2 boost-devel boost-build boost-python numpy \
    gcc git curl make zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl openssl-devel \
    wget python-devel libpng-devel freetype-devel git libtool python27-numpy \
	libtiff pkgconfig jasper libjpeg8 libjpeg-turbo-devel giflib-devel libwebp-devel PyOpenGL \
	mesa-libGLw freeglut-devel jasper-devel glew-devel xorg-x11-util-macros

RUN	yum -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm && \
	yum -y install OpenColorIO OpenColorIO-tools OpenImageIO-utils python-OpenImageIO && \
	yum -y autoremove && \
	yum clean all && \
    rm -rf /var/cache/yum

RUN useradd -m python_user

WORKDIR /home/python_user
USER python_user

RUN git clone git://github.com/pyenv/pyenv.git .pyenv

ENV HOME  /home/python_user
ENV PYENV_ROOT $HOME/.pyenv
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH
ENV PYTHONPATH /usr/lib64/python2.7/site-packages:$PYTHONPATH

RUN pyenv install 2.7.16
RUN pyenv global 2.7.16
RUN pyenv rehash

FROM centos:centos7 AS runtime-image

COPY --from=compile-image /home/python_user /home/python_user
COPY --from=compile-image /usr/lib64 /usr/lib64
COPY --from=compile-image /usr/bin/oiiotool /usr/bin/oiiotool
COPY --from=compile-image /usr/bin/ociobakelut /usr/bin/ociobakelut
COPY --from=compile-image /usr/bin/ociocheck /usr/bin/ociocheck
COPY --from=compile-image /usr/bin/ocioconvert /usr/bin/ocioconvert
COPY --from=compile-image /usr/bin/ociodisplay /usr/bin/ociodisplay
COPY --from=compile-image /usr/bin/ociolutimage  /usr/bin/ociolutimage

ENV PATH=/usr/bin:$PATH
ENV HOME  /home/python_user
ENV PYENV_ROOT $HOME/.pyenv
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH
ENV PYTHONPATH /usr/lib64/python2.7/site-packages:$PYTHONPATH
RUN useradd -m python_user

WORKDIR /home/python_user
USER python_user

ENTRYPOINT ["python"]