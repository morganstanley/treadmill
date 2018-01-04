#!/bin/sh

SCRIPT_NAME="${0##*/}"
SCRIPT_DIR="${0%/$SCRIPT_NAME}"

exec {{ _alias.pid1 }} -m -p "${SCRIPT_DIR}/run_real.sh"
