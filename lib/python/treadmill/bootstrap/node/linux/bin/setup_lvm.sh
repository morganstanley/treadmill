#!/bin/sh

# Set up LVM on node

{{ s6 }}/bin/s6-envdir {{ dir }}/env                                       \
{% if localdisk_block_dev %}
    {{ treadmill }}/bin/treadmill --debug admin node                       \
    lvm device                                                             \
    --device-name {{ localdisk_block_dev }}
{% else %}
    {{ treadmill }}/bin/treadmill --debug admin node                       \
    lvm image                                                              \
    --image-path {{ localdisk_img_location }}                              \
    --image-size {{ localdisk_img_size }}
{% endif %}
