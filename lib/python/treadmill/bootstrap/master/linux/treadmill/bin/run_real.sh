#!/bin/sh

# This script is not in chroot yet, so need to resolve local directory.

CHROOT={{ _alias.chroot }}
CHMOD={{ _alias.chmod }}
ECHO={{ _alias.echo }}
GREP={{ _alias.grep }}
LS={{ _alias.ls }}
MKDIR={{ _alias.mkdir }}
MOUNT={{ _alias.mount }}
RM={{ _alias.rm }}

# Look at ALL directories
unset KRB5CCNAME
unset KRB5_KTNAME

for SVC in $($LS {{ dir }}/treadmill/init); do
    $GREP {{ dir }}/treadmill/init/$SVC/\$ {{ dir }}/.install > /dev/null
    if [ $? != 0 ]; then
        $ECHO Removing extra service: $SVC
        $RM -vrf {{ dir }}/treadmill/init/$SVC
    fi
done

$RM -vf {{ dir }}/treadmill/init/*/data/exits/*

# Look at ALL directories, e.g. .mslinks
for DIR in $(ls -a /); do
    # Ignore . and .. directories
    if [[ "${DIR}" != "." && "${DIR}" != ".." && -d /${DIR} ]]; then
        $MKDIR -p {{ dir }}/${DIR}
        if [ $DIR == "tmp" ]; then
            # Make /tmp in chroot rw for all with sticky bit.
            $CHMOD 1777 {{ dir }}/$DIR
        else
            $MOUNT -n --rbind /${DIR} {{ dir }}/${DIR}
        fi
    fi
done

cd {{ dir }}

# Starting svscan
export PATH={{ _alias.s6 }}/bin:$PATH
exec \
    ${CHROOT} {{ dir }} \
    {{ _alias.s6_envdir }} /treadmill/env \
    {{ _alias.s6_svscan }} /treadmill/init
