#!/bin/sh

exec {{ pid1 }} -m -p ${0%.sh}_real.sh
