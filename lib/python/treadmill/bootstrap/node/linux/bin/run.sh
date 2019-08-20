#!/bin/sh

usage() {
    echo -n "Usage: $0 -n NOFILE_SLIMIT "
    exit 1
}

while getopts "n:" OPT; do
    case "${OPT}" in
        n)
            echo "Setting ulimit -Sn ${OPTARG}"
            ulimit -Sn ${OPTARG}
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))

# S6 needs to be in the PATH to function.
export PATH="{{ _alias.s6 }}/bin:${PATH}"

# Exec into real run script with environment setup.
exec \
    "{{ _alias.s6_envdir }}" "{{ dir }}/env" \
        "{{ dir }}/bin/run_real.sh"
