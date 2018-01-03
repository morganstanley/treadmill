#!/bin/bash -e

EXISTING='Use existing'
NEW='Create new'
EXIT='Exit'

function generate_key {
    echo "Generating new GPG key"
    gpg --gen-key

    echo "Enter your GPG key name. Format: Name <foo@bar.com>"
    read keyname
    echo "%_gpg_name $keyname" >> ~/.rpmmacros

    echo "Generating public key in $(pwd)"
    gpg --export -a $keyname > RPM-GPG-KEY-TREADMILL
}


if (grep "%_gpg_name" ~/.rpmmacros) then
    echo "~/.rpmmacros file already has a GPG key."

    select response in "$EXISTING" "$NEW" "$EXIT":
    do case $response in
            $EXISTING)
                rpm --addsign $@
                exit 0
                ;;
            $NEW)
                sed -i '\/%_gpg_name/d' ~/.rpmmacros
                generate_key
                rpm --addsign $@
                exit 0
                ;;
            *)
                echo 'Exiting.'
                exit 1
        esac
    done
else
    generate_key
    rpm --addsign $@
fi
