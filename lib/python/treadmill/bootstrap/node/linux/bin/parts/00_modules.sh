# Load required additionnal kernel modules

ECHO="{{ _alias.echo }}"
GREP="{{ _alias.grep }}"
MODPROBE="{{ _alias.modprobe }}"


set -e

###############################################################################
function init_modules_rhel6() {
    # Load connection tracking for GRE tunnels
    ${MODPROBE} nf_conntrack_proto_gre
}

###############################################################################
function init_modules_rhel7() {
    # Load connection tracking for GRE tunnels
    ${MODPROBE} nf_conntrack_proto_gre
}

###############################################################################

if [ $(${GREP} -c "release 7" /etc/redhat-release) -ne 0 ]; then
    ${ECHO} "Loading for RHEL7 compatible modules."
    init_modules_rhel7
elif [ $(${GREP} -c "release 6" /etc/redhat-release) -ne 0 ]; then
    ${ECHO} "Configuring for RHEL6 compatible cgroups."
    init_modules_rhel6
else
    ${ECHO} "Unknown distribution release. Assuming RHEL7 compatible."
    init_modules_rhel7
fi
