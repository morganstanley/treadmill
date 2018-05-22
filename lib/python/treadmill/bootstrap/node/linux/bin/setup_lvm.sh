#!/bin/sh

# Set up LVM on node

{{ _alias.s6_envdir }} {{ dir }}/env                                       \
{% if localdisk_block_dev %}
    {{ treadmill }}/bin/treadmill --debug admin node                     \
    lvm                                                                    \
    --vg-name {{ localdisk_vg_name }}                                      \
    device                                                                 \
    --device-name {{ localdisk_block_dev }}
{% else %}
    {{ treadmill }}/bin/treadmill --debug admin node                     \
    lvm                                                                    \
    --vg-name {{ localdisk_vg_name }}                                      \
    image                                                                  \
    --image-path {{ localdisk_img_location }}                              \
    --image-size {{ localdisk_img_size }}
{% endif %}
