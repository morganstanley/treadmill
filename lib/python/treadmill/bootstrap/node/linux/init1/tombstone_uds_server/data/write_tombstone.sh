#!{{ _alias.execlineb }}

{{ _alias.withstdinas }} FILENAME
{{ _alias.importas }} -i -n FILENAME FILENAME
{{ _alias.touch }} {{ dir }}/tombstones/services/${FILENAME}
