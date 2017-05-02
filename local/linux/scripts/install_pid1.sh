#!/bin/bash -e

pid1_url="${1:-https://github.com/Morgan-Stanley/treadmill-pid1/archive/master.tar.gz}"

echo -e '\n\nDownloading treadmill pid1 - ' $pid1_url '...'
curl -L $pid1_url --output /tmp/treadmill-pid1.tar.gz

echo -e '\n\nExtracting treadmill pid1...'
tar -zxf /tmp/treadmill-pid1.tar.gz -C /tmp

echo -e '\n\nCompiling treadmill pid1...'
make -C /tmp/treadmill-pid1-master

mv /tmp/treadmill-pid1-master/pid1 /bin/

echo -e '\n\nCleaning up...'
rm -rf /tmp/treadmill-pid1.tar.gz
rm -rf /tmp/treadmill-pid1-master

echo -e '\n\nSuccessfully installed!'
