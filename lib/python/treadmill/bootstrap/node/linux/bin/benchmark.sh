#!/bin/sh

UNSHARE={{ _alias.unshare }}

# Make sure we have LVM set up on node
{{ s6 }}/bin/s6-envdir {{ dir }}/env                                           \
{{ dir }}/bin/setup_lvm.sh

# Benchmark disk io throughput of the LVM
{{ s6 }}/bin/s6-envdir {{ dir }}/env                                           \
$UNSHARE --mount {{ treadmill }}/bin/treadmill --debug admin node              \
    benchmark                                                                  \
    --benchmark-publish-file {{ block_dev_configuration }}                     \
{%- if localdisk_block_dev %}
    --underlying-device-name {{ localdisk_block_dev }}                         \
{%- endif %}
{%- if localdisk_img_location %}
    --underlying-image-path {{ localdisk_img_location }}
{%- endif %}
