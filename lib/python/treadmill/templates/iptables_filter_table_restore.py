"""Iptables filter restore table template."""

T = """
*filter
:REJECT_N_LOG_FORWARD - [0:0]
-F REJECT_N_LOG_FORWARD
-A REJECT_N_LOG_FORWARD -j LOG --log-prefix "00000000R FORWARD packets: " \
    --log-level debug
-A REJECT_N_LOG_FORWARD -j REJECT

:DROP_N_LOG_FORWARD - [0:0]
-F DROP_N_LOG_FORWARD
-A DROP_N_LOG_FORWARD -j LOG --log-prefix "00000000D FORWARD packets: " \
    --log-level debug
-A DROP_N_LOG_FORWARD -j DROP

:LOG_N_LOG_FORWARD - [0:0]
-F LOG_N_LOG_FORWARD
-A LOG_N_LOG_FORWARD -j LOG --log-prefix "00000000L FORWARD packets: " \
    --log-level debug

:ACCEPT_N_LOG_FORWARD - [0:0]
-F ACCEPT_N_LOG_FORWARD
-A ACCEPT_N_LOG_FORWARD -j LOG --log-prefix "00000000A FORWARD packets: " \
    --log-level debug
-A ACCEPT_N_LOG_FORWARD -j ACCEPT

{% if filter_in_nonprod_chain -%}
:TM_FILTER_IN_NONPROD - [0:0]
-F TM_FILTER_IN_NONPROD
-A TM_FILTER_IN_NONPROD -m set --match-set {{any_container}} src -j RETURN
{%- for filter_rule in filter_in_nonprod_chain %}
-A TM_FILTER_IN_NONPROD {{filter_rule}}
{%- endfor -%}
{%- endif %}

{% if filter_out_nonprod_chain -%}
:TM_FILTER_OUT_NONPROD - [0:0]
-F TM_FILTER_OUT_NONPROD
-A TM_FILTER_OUT_NONPROD -m set --match-set {{any_container}} dst -j RETURN
{%- for filter_rule in filter_out_nonprod_chain %}
-A TM_FILTER_OUT_NONPROD {{filter_rule}}
{%- endfor -%}
{%- endif %}

:TM_FILTER - [0:0]
-F TM_FILTER
-A TM_FILTER -m state --state ESTABLISHED,RELATED -j ACCEPT
-A TM_FILTER -m state --state INVALID -j DROP_N_LOG_FORWARD
-A TM_FILTER -m state --state NEW -m set \
    --match-set {{infra_services}} dst,dst -j ACCEPT
-A TM_FILTER -j {{ filter_exception_chain }}
-A TM_FILTER -m state --state NEW -m connmark --mark {{nonprod_mark}} -m set \
    --match-set {{prod_containers}} dst -j REJECT_N_LOG_FORWARD
-A TM_FILTER -m state --state NEW -m connmark --mark {{nonprod_mark}} \
    -j TM_FILTER_OUT_NONPROD
-A TM_FILTER -m state --state NEW \
    -m set --match-set {{nonprod_containers}} dst \
    -j TM_FILTER_IN_NONPROD

:FORWARD ACCEPT [0:0]
-F FORWARD
-A FORWARD -j TM_FILTER

COMMIT
"""
