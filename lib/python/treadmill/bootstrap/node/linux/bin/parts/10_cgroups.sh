# This carves the system in 2: system and treadmill.
#
# At the end of this script, all enabled/supported cgroups will be setup under
# /sys/fs/cgroup (mimicing modern linux distros), the configured limit will be
# applied to the relevant cgroups and the current process and its parent will
# have joined the $TREADMILL_ROOT_CGROUP cgroup for each of the supported
# cgroup subsystem.

AWK="{{ _alias.awk }}"
CAT="{{ _alias.cat }}"
CGCLEAR="{{ _alias.cgclear }}"
ECHO="{{ _alias.echo }}"
FIND="{{ _alias.find }}"
GREP="{{ _alias.grep }}"
LS="{{ _alias.ls }}"
MKDIR="{{ _alias.mkdir }}"
MOUNT="{{ _alias.mount }}"
RMDIR="{{ _alias.rmdir }}"

set -e

TREADMILL_ROOT_CGROUP="treadmill"

###############################################################################
TREADMILL_CPUSHARE="{{ treadmill_cpu_shares }}"
TREADMILL_CPUSHARE="${TREADMILL_CPUSHARE%%%}"
SYSTEM_CPUSHARE="$((100-${TREADMILL_CPUSHARE}))"

###############################################################################
TREADMILL_CPUSET_CORES="{{ treadmill_cpuset_cores }}"
SYSTEM_CPUSET_CORES="{{ system_cpuset_cores }}"

###############################################################################
TREADMILL_MEMORY="{{ treadmill_mem }}"
if [ "${TREADMILL_MEMORY##-}" != "${TREADMILL_MEMORY}" ]; then
    SYSTEM_MEMORY="${TREADMILL_MEMORY##-}"
    TREADMILL_MEMORY="-1"
else
    SYSTEM_MEMORY="-1"
fi
###############################################################################


###############################################################################
function init_cgroup_rhel7() {
    # RHEL7 has a proper layout of cgroups. Only worry about applying
    # configurations to the cgroups and joining the $TREADMILL_ROOT_CGROUP.

    # NOTE: Most of this should be done in the system launching Treadmill
    # (systemd unit?)

    CGROUP_BASE="/sys/fs/cgroup"
    CPUSET_ALL_CORES="$(${CAT} ${CGROUP_BASE}/cpuset/cpuset.cpus)"
    if [ -z "${TREADMILL_CPUSET_CORES}" ]; then
        TREADMILL_CPUSET_CORES=${CPUSET_ALL_CORES}
    fi
    if [ -z "${SYSTEM_CPUSET_CORES}" ]; then
        SYSTEM_CPUSET_CORES=${CPUSET_ALL_CORES}
    fi

    # Special config for the memory cgroup
    ${ECHO} "Setting memory cgroup options"
    ${ECHO} 1 >${CGROUP_BASE}/memory/memory.use_hierarchy
    ${ECHO} 1 >${CGROUP_BASE}/memory/memory.move_charge_at_immigrate

    ${ECHO} "Setting cpuset cgroup options"
    ${ECHO} 1 >${CGROUP_BASE}/cpuset/cgroup.clone_children

    CGROUPS=$(${ECHO} ${CGROUP_BASE}/*/)
    for CGROUP in ${CGROUPS}; do

        # Skip the special systemd cgroup.
        if [ ${CGROUP%%systemd/} != ${CGROUP} ]; then
            continue
        fi

        # Move all current tasks to the system.slice cgroup
        ${MKDIR} -vp ${CGROUP}/system.slice

        # Setup memory cgroup options for system.slice
        if [ ${CGROUP%%memory/} != ${CGROUP} ]; then
            ${ECHO} "Setting up ${CGROUP}/system.slice"
            ${ECHO} 1 >${CGROUP}/system.slice/memory.move_charge_at_immigrate
        fi

        for P in $(${CAT} ${CGROUP}/tasks); do
            # Skipt kernel processes.
            if [ -z "$(${CAT} /proc/${P}/cmdline)" ]; then
                continue
            fi
            ${ECHO} "Moving ${P} to ${CGROUP}/system.slice"
            ${ECHO} ${P} >${CGROUP}/system.slice/tasks
        done
    done

    # Create a treadmill group
    for CGROUP in ${CGROUPS}; do

        # Skip the special systemd cgroup.
        if [ ${CGROUP%%systemd/} != ${CGROUP} ]; then
            continue
        fi

        ${MKDIR} -vp ${CGROUP}/${TREADMILL_ROOT_CGROUP}

        # Setup memory cgroup options for Treadmill cgroup.
        if [ ${CGROUP%%memory/} != ${CGROUP} ]; then
            ${ECHO} "Setting up ${CGROUP}/${TREADMILL_ROOT_CGROUP}"
            ${ECHO} 1 >${CGROUP}/${TREADMILL_ROOT_CGROUP}/memory.move_charge_at_immigrate
        fi

        # Cleanup all existing Treadmill cgroups
        ${ECHO} "Cleaning up ${CGROUP}/${TREADMILL_ROOT_CGROUP}"
        ${FIND} ${CGROUP}/${TREADMILL_ROOT_CGROUP} \
            -depth \
            -mindepth 1\
            -type d \
            -delete

        # Adding current and parent PID (main script) to the ${TREADMILL_ROOT_CGROUP}.
        ${ECHO} "Entering ${CGROUP}/${TREADMILL_ROOT_CGROUP}"
        ${ECHO} ${$} >${CGROUP}/${TREADMILL_ROOT_CGROUP}/tasks
        ${ECHO} ${PPID} >${CGROUP}/${TREADMILL_ROOT_CGROUP}/tasks
    done

    ${ECHO} "Setting system CPU shares: ${SYSTEM_CPUSHARE}%"
    ${ECHO} "Setting Treadmill CPU shares: ${TREADMILL_CPUSHARE}%"
    ${ECHO} ${SYSTEM_CPUSHARE} >${CGROUP_BASE}/cpu/system.slice/cpu.shares
    ${ECHO} ${TREADMILL_CPUSHARE} >${CGROUP_BASE}/cpu/treadmill/cpu.shares

    ${ECHO} "Setting system CPU set: ${SYSTEM_CPUSET_CORES}"
    ${ECHO} "Setting Treadmill CPU set: ${TREADMILL_CPUSET_CORES}"
    ${ECHO} ${SYSTEM_CPUSET_CORES} >${CGROUP_BASE}/cpuset/system.slice/cpuset.cpus
    ${ECHO} ${TREADMILL_CPUSET_CORES} >${CGROUP_BASE}/cpuset/treadmill/cpuset.cpus

    ${ECHO} "Setting system memory: ${SYSTEM_MEMORY}"
    ${ECHO} "Setting Treadmill memory: ${TREADMILL_MEMORY}"
    ${ECHO} ${SYSTEM_MEMORY} >${CGROUP_BASE}/memory/system.slice/memory.limit_in_bytes
    ${ECHO} ${TREADMILL_MEMORY} >${CGROUP_BASE}/memory/treadmill/memory.limit_in_bytes

    systemctl set-property --runtime system.slice CPUAccounting=true
    systemctl set-property --runtime system.slice MemoryAccounting=true
    systemctl set-property --runtime system.slice MemoryLimit=${SYSTEM_MEMORY}
    systemctl set-property --runtime system.slice BlockIOAccounting=true
}

###############################################################################
function init_cgroup_rhel6() {
    SYS_FS='/sys/fs'
    CGROUP_BASE="${SYS_FS}/cgroup"
    MOUNTINFO='/proc/self/mountinfo'
    MNT_BASE='/mnt'

    # clear existing cgroup mount/setting
    # if no cgroup mounted, cgclear returns 3 but we do not care
    ${ECHO} "Calling ${CGCLEAR} to clear cgroup mount/setting"
    set +e
    ${CGCLEAR}
    set -e

    # mount /mnt/cgroup on /sys/fs/cgroup
    if [ ! -d ${CGROUP_BASE} ]; then
        if [ -z "$(${CAT} ${MOUNTINFO}|${GREP} -w ${MNT_BASE})" ]; then
            ${MOUNT} tmpfs ${MNT_BASE} -t tmpfs -o 'rw,nosuid,nodev,noexec,mode=755'
        fi
        ${MKDIR} -vp ${MNT_BASE}/cgroup

        # even FS path is not mounted. it is not a big problem
        SYSFS_PATHS=$(${LS} ${SYS_FS}/)
        for FSPATH in ${SYSFS_PATHS}; do
            # we ignore /sys/fs/cgroup
            if [ ${FSPATH%%cgroup/} != ${FSPATH} ]; then
                continue
            fi

            if [ ! -d ${MNT_BASE}/${FSPATH} ]; then
                ${MKDIR} -vp ${MNT_BASE}/${FSPATH}
                ${MOUNT} -o bind ${SYS_FS}/${FSPATH} ${MNT_BASE}/${FSPATH}
            fi
        done

        # move mount /mnt/cgroup to /sys/fs/cgroup
        ${MOUNT} --move ${MNT_BASE} ${SYS_FS}
    fi

    # mount every cgroup to /sys/fs/cgroup
    AVAILABLES=$(${CAT} /proc/cgroups|${GREP} -v subsys_name|${AWK} '{print $1}')
    for AVAIL in ${AVAILABLES}; do
        # we ignore ns cgroup, it is not available in RH6
        if [ "x${AVAIL}" == "xns" ]; then
            continue
        fi

        if [ ! -d ${CGROUP_BASE}/${AVAIL} ]; then
            ${MKDIR} ${CGROUP_BASE}/${AVAIL}
        fi

        # cgcleared, always mount path
        ${ECHO} "mounting ${CGROUP_BASE}/${AVAIL}"
        ${MOUNT} ${AVAIL} ${CGROUP_BASE}/${AVAIL} -o "rw,nosuid,nodev,noexec,relatime,$AVAIL" -t cgroup
    done

    # remount as readonly
    ${MOUNT} -o remount,ro ${SYS_FS}

    CPUSET_ALL_CORES="$(${CAT} ${CGROUP_BASE}/cpuset/cpuset.cpus)"
    if [ -z "${TREADMILL_CPUSET_CORES}" ]; then
        TREADMILL_CPUSET_CORES=${CPUSET_ALL_CORES}
    fi
    if [ -z "${SYSTEM_CPUSET_CORES}" ]; then
        SYSTEM_CPUSET_CORES=${CPUSET_ALL_CORES}
    fi

    # Special config for the memory cgroup
    ${ECHO} 1 >${CGROUP_BASE}/memory/memory.use_hierarchy
    ${ECHO} 1 >${CGROUP_BASE}/memory/memory.move_charge_at_immigrate
    # There is no cpuset/cgroup.clone_children in RH6

    CGROUPS=$(${ECHO} ${CGROUP_BASE}/*/)
    cpuset_mems=$(${CAT} ${CGROUP_BASE}/cpuset/cpuset.mems)

    # move system pid to system.slice
    for CGROUP in ${CGROUPS}; do
        # Move all current tasks to the system.slice cgroup
        ${MKDIR} -vp ${CGROUP}/system.slice

        # Setup memory cgroup options for system.slice
        if [ ${CGROUP%%memory/} != ${CGROUP} ]; then
            ${ECHO} "Setting up ${CGROUP}/system.slice"
            ${ECHO} 1 >${CGROUP}/system.slice/memory.move_charge_at_immigrate
        fi

        # set cpuset.cpus and cpuset.mems otherwise tasks is not writable
        if [ ${CGROUP%%cpuset/} != ${CGROUP} ]; then
            ${ECHO} "Setting Treadmill CPU set: ${TREADMILL_CPUSET_CORES}"
            ${ECHO} ${SYSTEM_CPUSET_CORES} >${CGROUP}/system.slice/cpuset.cpus
            ${ECHO} "Setting system CPU set mem: ${cpuset_mems}"
            ${ECHO} ${cpuset_mems} >${CGROUP}/system.slice/cpuset.mems
        fi

        for P in $(${CAT} ${CGROUP}/tasks); do
            # Skipt kernel processes.
            if [ -z "$(${CAT} /proc/${P}/cmdline)" ]; then
                continue
            fi
            ${ECHO} "Moving ${P} to ${CGROUP}/system.slice"
            ${ECHO} ${P} >${CGROUP}/system.slice/tasks
        done
    done

    # setup treadmill subgroup in each cgroup subsystem
    for CGROUP in ${CGROUPS}; do
        ${MKDIR} -vp ${CGROUP}/${TREADMILL_ROOT_CGROUP}

        # Setup memory cgroup options for Treadmill cgroup.
        if [ ${CGROUP%%memory/} != ${CGROUP} ]; then
            ${ECHO} "Setting up ${CGROUP}/${TREADMILL_ROOT_CGROUP}"
            ${ECHO} 1 >${CGROUP}/${TREADMILL_ROOT_CGROUP}/memory.move_charge_at_immigrate
        fi

        if [ ${CGROUP%%cpuset/} != ${CGROUP} ]; then
            ${ECHO} "Setting system CPU set: ${SYSTEM_CPUSET_CORES}"
            ${ECHO} ${TREADMILL_CPUSET_CORES} >${CGROUP}/${TREADMILL_ROOT_CGROUP}/cpuset.cpus
            ${ECHO} "Setting Treadmill CPU set mem: ${cpuset_mems}"
            ${ECHO} ${cpuset_mems} >${CGROUP}/${TREADMILL_ROOT_CGROUP}/cpuset.mems
        fi

        # Adding current and parent PID (main script) to the ${TREADMILL_ROOT_CGROUP}.
        ${ECHO} "Entering ${CGROUP}/${TREADMILL_ROOT_CGROUP}"
        ${ECHO} ${$} >${CGROUP}/${TREADMILL_ROOT_CGROUP}/tasks
        ${ECHO} ${PPID} >${CGROUP}/${TREADMILL_ROOT_CGROUP}/tasks
    done

    ${ECHO} "Setting system CPU shares: ${SYSTEM_CPUSHARE}%"
    ${ECHO} "Setting Treadmill CPU shares: ${TREADMILL_CPUSHARE}%"
    ${ECHO} ${SYSTEM_CPUSHARE} >${CGROUP_BASE}/cpu/system.slice/cpu.shares
    ${ECHO} ${TREADMILL_CPUSHARE} >${CGROUP_BASE}/cpu/treadmill/cpu.shares
}

###############################################################################

if [ $(${GREP} -c "release 7" /etc/redhat-release) -ne 0 ]; then
    ${ECHO} "Configuring for RHEL7 compatible cgroups."
    init_cgroup_rhel7
elif [ $(${GREP} -c "release 6" /etc/redhat-release) -ne 0 ]; then
    ${ECHO} "Configuring for RHEL6 compatible cgroups."
    init_cgroup_rhel6
else
    ${ECHO} "Unknown distribution release. Assuming RHEL7 compatible."
    init_cgroup_rhel7
fi
