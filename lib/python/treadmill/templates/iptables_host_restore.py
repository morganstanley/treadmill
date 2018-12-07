"""IPtables host restore template."""

T = """
*raw
:PREROUTING ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
COMMIT

*mangle
:TM_MARK_NONPROD - [0:0]
-F TM_MARK_NONPROD
-A TM_MARK_NONPROD -j CONNMARK --set-mark {{nonprod_mark}}
-A TM_MARK_NONPROD -j ACCEPT

:TM_MARK_PROD - [0:0]
-F TM_MARK_PROD
-A TM_MARK_PROD -j CONNMARK --set-mark {{prod_mark}}
-A TM_MARK_PROD -j ACCEPT

:TM_MARK_NODES - [0:0]
-F TM_MARK_NODES
-A TM_MARK_NODES -s {{external_ip}} -j TM_MARK_PROD
-A TM_MARK_NODES -p tcp -m tcp \
    --source-port {{prod_low|int}}:{{prod_high|int}} -j TM_MARK_PROD
-A TM_MARK_NODES -p udp -m udp \
    --source-port {{prod_low|int}}:{{prod_high|int}} -j TM_MARK_PROD
-A TM_MARK_NODES -p tcp -m tcp \
    --source-port {{nonprod_low|int}}:{{nonprod_high|int}} -j TM_MARK_NONPROD
-A TM_MARK_NODES -p udp -m udp \
    --source-port {{nonprod_low|int}}:{{nonprod_high|int}} -j TM_MARK_NONPROD

:TM_MARK - [0:0]
-F TM_MARK
-A TM_MARK -m state --state ESTABLISHED,RELATED -j ACCEPT
-A TM_MARK -m state --state NEW -m set \
    --match-set {{prod_containers}} src -j TM_MARK_PROD
-A TM_MARK -m state --state NEW -m set \
    --match-set {{nonprod_containers}} src -j TM_MARK_NONPROD
-A TM_MARK -m state --state NEW -m set \
    --match-set {{nodes}} src -j TM_MARK_NODES
-A TM_MARK -m state --state NEW -m set \
    --match-set {{prod_sources}} src -j TM_MARK_PROD
-A TM_MARK -m state --state NEW -m set ! \
    --match-set {{prod_sources}} src -j TM_MARK_NONPROD

:FORWARD ACCEPT [0:0]
-F FORWARD
-A FORWARD -j TM_MARK

:OUTPUT ACCEPT [0:0]
-F OUTPUT
-A OUTPUT -d {{external_ip}} -j TM_MARK
COMMIT

*nat
:{{passthrough_chain}} - [0:0]

:{{dnat_chain}} - [0:0]

:{{snat_chain}} - [0:0]

:{{vring_dnat_chain}} - [0:0]

:{{vring_snat_chain}} - [0:0]

:TM_POSTROUTING_PASSTHROUGH - [0:0]
-F TM_POSTROUTING_PASSTHROUGH
-A TM_POSTROUTING_PASSTHROUGH -p udp -j SNAT --to-source {{external_ip}}
-A TM_POSTROUTING_PASSTHROUGH -p tcp -j SNAT --to-source {{external_ip}}

:TM_POSTROUTING_PROD - [0:0]
-F TM_POSTROUTING_PROD
-A TM_POSTROUTING_PROD -p icmp --icmp-type any -j SNAT \
    --to-source {{external_ip}}
-A TM_POSTROUTING_PROD -p udp -j SNAT \
    --to-source {{external_ip}}:{{prod_low|int}}-{{prod_high|int}}
-A TM_POSTROUTING_PROD -p tcp -j SNAT \
    --to-source {{external_ip}}:{{prod_low|int}}-{{prod_high|int}}
-A TM_POSTROUTING_PROD -p gre -j SNAT \
    --to-source {{external_ip}}

:TM_POSTROUTING_NONPROD - [0:0]
-F TM_POSTROUTING_NONPROD
-A TM_POSTROUTING_NONPROD -p icmp --icmp-type any -j SNAT \
    --to-source {{external_ip}}
-A TM_POSTROUTING_NONPROD -p udp -j SNAT \
    --to-source {{external_ip}}:{{nonprod_low|int}}-{{nonprod_high|int}}
-A TM_POSTROUTING_NONPROD -p tcp -j SNAT \
    --to-source {{external_ip}}:{{nonprod_low|int}}-{{nonprod_high|int}}
-A TM_POSTROUTING_NONPROD -p gre -j SNAT \
    --to-source {{external_ip}}

:TM_POSTROUTING_CONTAINER - [0:0]
-F TM_POSTROUTING_CONTAINER
-A TM_POSTROUTING_CONTAINER -m set --match-set {{passthroughs}} dst \
    -j TM_POSTROUTING_PASSTHROUGH
-A TM_POSTROUTING_CONTAINER -j {{snat_chain}}
-A TM_POSTROUTING_CONTAINER -m connmark --mark {{nonprod_mark}} \
    -j TM_POSTROUTING_NONPROD
-A TM_POSTROUTING_CONTAINER -m connmark --mark {{prod_mark}} \
    -j TM_POSTROUTING_PROD

:POSTROUTING ACCEPT [0:0]
-F POSTROUTING
-A POSTROUTING -m set --match-set {{any_container}} src \
    -j TM_POSTROUTING_CONTAINER
-A POSTROUTING -m set --match-set {{vring_containers}} dst \
    -j {{vring_snat_chain}}

:TM_SERVICES - [0:0]
-F TM_SERVICES
-A TM_SERVICES -p tcp -m tcp --dport 13684 -j DNAT \
    --to-destination 127.0.0.1:13684
-A TM_SERVICES -p tcp -m tcp --dport 13685 -j DNAT \
    --to-destination 127.0.0.1:13685

:PREROUTING ACCEPT [0:0]
-F PREROUTING
-A PREROUTING -m set --match-set {{any_container}} \
    src -d 192.168.10.10 -j TM_SERVICES
-A PREROUTING -m set --match-set {{passthroughs}} \
    src -j {{passthrough_chain}}
-A PREROUTING -m set --match-set {{vring_containers}} \
    src -j {{vring_dnat_chain}}
-A PREROUTING -j {{dnat_chain}}

:OUTPUT ACCEPT [0:0]
-F OUTPUT
-A OUTPUT -d {{external_ip}} -j {{dnat_chain}}
COMMIT
"""
