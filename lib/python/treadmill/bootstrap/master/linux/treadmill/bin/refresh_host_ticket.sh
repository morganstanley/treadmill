#!/bin/sh

# Creates / refresh host ticket from host keytab.
#
# Usage:
#   refresh_host_ticket.sh
#

set -e
set -x

source "/treadmill/bin/parts/10_host_tickets.sh"

for (( ; ; ))
do
    # Sleep 3 hours (60 * 60 * 3)
    sleep 10800

    refresh_host_ticket
done
