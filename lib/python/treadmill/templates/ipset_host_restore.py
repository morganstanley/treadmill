"""IPSet host restore template."""

T = """
create {{any_container}} list:set size 8
create {{infra_services}} hash:ip,port family inet hashsize 1024 maxelem 65536
create {{nonprod_containers}} hash:ip family inet hashsize 1024 maxelem 65536
create {{prod_containers}} hash:ip family inet hashsize 1024 maxelem 65536
create {{passthroughs}} hash:ip family inet hashsize 1024 maxelem 65536
create {{nodes}} hash:ip family inet hashsize 1024 maxelem 65536
create {{prod_sources}} hash:ip family inet hashsize 4096 maxelem 262144
create {{vring_containers}} hash:ip family inet hashsize 1024 maxelem 65536
"""
