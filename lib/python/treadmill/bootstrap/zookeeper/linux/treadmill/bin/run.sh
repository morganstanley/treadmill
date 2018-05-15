#!/bin/sh

exec {{ _alias.pid1 }} \
    --propagation=slave \
    -m -p \
    ${0%.sh}_real.sh
