#!/bin/sh -e

# Configure /a as shared mount point so that automount works inside the
# Treadmill containers.
#

MOUNT="/bin/mount -v"
CHMOD="/bin/chmod -v"
MKDIR="/bin/mkdir -v"
TOUCH=/bin/touch
CAT=/bin/cat
CUT=/usr/bin/cut
GREP=/bin/grep
KILL=/bin/kill
AMQ=/ms/dist/aurora/PROJ/amd/prod/sbin/amq

echo Using $(${MOUNT} -V)

# Ensure that /a is properly setup for Treadmill
#
# Do nothing if '/a' is already mounted (assume it is setup properly)
#
# Otherwise, make sure the directory it exists, rbind it to itself so that
# it exists as a mount endpoint (this also prevents amd from removing the
# directory), and mark that mountpoint as a share mount point.
#
# Once this is all done, kill -HUP automounter so that it restarts (with the
# now properly setup mount point).
#
function make_a_shared_mount {
    # See if the /a  mount point is already mounted
    local A_MOUNTED="$(${CAT} /etc/mtab | \
                       ${CUT} -d ' ' -f 2 | ${GREP} -E "^/a$" 2>/dev/null)"

    if [ -z "${A_MOUNTED}" ]; then
        ${MKDIR} -p /a
        ${MOUNT} --rbind /a /a >/dev/null
        echo Creating /a mount point with \"${MOUNT} --rbind /a /a\" -\> $?
    else
        echo \'/a\' is already mounted.
    fi

    ${MOUNT} --make-shared /a
    echo Setting /a as shared with \"${MOUNT} --make-shared /a\" -\> $?

    # Ask the amounter to restart
    AMD_PID=$(${AMQ} -p)
    ${KILL} -HUP ${AMD_PID}
    echo Asking Automounter at PID ${AMD_PID} to reload -\> $?
}

make_a_shared_mount
