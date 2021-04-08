FROM aswf/ci-vfxall:2021-clang10.5 AS compile-image

RUN pip install "pybind11" && \
    pip3 install "pybind11"

RUN useradd -m build_user
WORKDIR /home/build_user

RUN git clone https://github.com/OpenImageIO/oiio.git && \
    cd oiio && \
    sh ./src/build-scripts/build_pybind11.bash && \
    mkdir build && \
    cd build && \
    cmake .. -Dpybind11_DIR=/home/python_user/.local/lib/python3.7/site-packages -DOIIO_BUILD_TOOLS=ON && \
    make && \
    make install


FROM centos:centos7 AS runtime-image

COPY --from=compile-image /bin /bin
COPY --from=compile-image /usr/lib /usr/lib
COPY --from=compile-image /usr/lib64 /usr/lib64
COPY --from=compile-image /usr/bin /usr/bin
COPY --from=compile-image /usr/include /usr/include
COPY --from=compile-image /usr/share /usr/share
COPY --from=compile-image /usr/local/include /usr/local/include
COPY --from=compile-image /usr/local/lib64 /usr/local/lib64
COPY --from=compile-image /usr/local/bin /usr/local/bin
COPY --from=compile-image /usr/local/lib /usr/local/lib
COPY --from=compile-image /home/build_user/oiio/build/bin /usr/local/bin

ENV PATH=/usr/bin:/usr/local/bin:$PATH

RUN useradd -m algernon
USER algernon
ENV HOME  /home/algernon
