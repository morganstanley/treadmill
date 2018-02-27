#!/bin/sh

# Creates / refresh host ticket from host keytab.
#
# Usage:
#   refresh_host_ticket.sh
#

set -e
set -x

source "{{ dir }}/bin/parts/40_host_tickets.sh"

for (( ; ; ))
do
    # Sleep 10 hours (60 * 60 * 10)
    sleep 36000

    refresh_host_ticket
done
