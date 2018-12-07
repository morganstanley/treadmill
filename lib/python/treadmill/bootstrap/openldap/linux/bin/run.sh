#!/bin/sh

# S6 needs to be in the PATH to function.
export PATH="{{ _alias.s6 }}/bin:${PATH}"

# Exec into real run script with environment setup.
exec \
    "{{ _alias.s6_envdir }}" "{{ dir }}/env" \
        "{{ dir }}/bin/run_real.sh"
