#!/bin/sh

UNSHARE={{ _alias.unshare }}

# Make sure we have LVM set up on node
{{ dir }}/bin/setup_lvm.sh

# Benchmark disk io throughput of the LVM
{{ s6 }}/bin/s6-envdir {{ dir }}/env                                           \
$UNSHARE --mount {{ treadmill }}/bin/treadmill --debug admin node              \
    benchmark                                                                  \
    --benchmark-publish-file {{ localdisk_benchmark_location }}                \
{%- if localdisk_block_dev %}
    --underlying-device-name {{ localdisk_block_dev }}                         \
{%- endif %}
{%- if localdisk_img_location %}
    --underlying-image-path {{ localdisk_img_location }}
{%- endif %}
