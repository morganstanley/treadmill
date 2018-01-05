#!/bin/sh

# Creates host tickets from host keytab.
#
# Usage:
# host_tickets.sh [-o] TICKET_FILE
#
# If -o (once) specified, generate tickets and exit, otherwise run in the
# loop, sleeping for 8 hours before refreshing tickets.

function usage() {
    echo "Usage: $0 [-or] TICKET_FILE"
    exit 0
}

while getopts ':orh' OPT
do
    case $OPT in
        'o')
            RUN_ONCE=1
            ;;
        'r')
            REFRESH_TICKETS=1
            ;;
        'h')
            usage
            ;;
        \?)
            echo "$0: Invalid option '-$OPTARG'" >&2
            exit 1
            ;;
    esac
done
shift $((OPTIND-1))

TICKET="$1"

if [ -z ${TICKET} ]
then
    usage
fi

export KRB5CCNAME="FILE:${TICKET}"
unset KRB5_KTNAME

for (( ; ; ))
do
    /bin/date

    # Ensure that there are no overrides that can affect dst operation.
    sed -i '/^krb5_keytab\s/d' /etc/services
    sed -i '/^srvtab_gen\s/d' /etc/services
    /ms/dist/sec/bin/dst -c
    /ms/dist/sec/PROJ/ksymlinks/incr/bin/kinit -k -l 2d

    # Display tickets cache and host keytabs for debugging purposes.
    /ms/dist/sec/PROJ/ksymlinks/incr/bin/klist -5
    /ms/dist/sec/PROJ/ksymlinks/incr/bin/klist -k

    if [ ! -z ${REFRESH_TICKETS} ]; then
        echo /ms/dist/kerberos/PROJ/scripts/incr/bin/ticket_wrapper
        /ms/dist/kerberos/PROJ/scripts/incr/bin/ticket_wrapper
    fi

    if [ ! -z ${RUN_ONCE} ]; then
        exit 0
    fi

    # Sleep 10 hours (60 * 60 * 10)
    echo sleep 36000
    sleep 36000
done
