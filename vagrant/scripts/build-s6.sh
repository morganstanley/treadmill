#/bin/bash

cd $(mktemp -d)

git clone --depth 1 https://github.com/skarnet/s6.git
git clone --depth 1 https://github.com/skarnet/skalibs.git
git clone --depth 1 https://github.com/skarnet/execline.git

cd skalibs
./configure --prefix=/opt/s6 && make && make install
cd -

cd execline
./configure --prefix=/opt/s6 \
        --with-include=/opt/s6/include \
        --with-lib=/opt/s6/lib/skalibs \
    && make && make install
cd -

cd s6
./configure --prefix=/opt/s6 \
        --with-include=/opt/s6/include \
        --with-lib=/opt/s6/lib/skalibs \
        --with-lib=/opt/s6/lib/execline \
    && make && make install
cd -
