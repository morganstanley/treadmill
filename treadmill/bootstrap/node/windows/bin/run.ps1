Get-ChildItem -Recurse "{{ dir }}\init\*\data\exits\*" | foreach ($_) {remove-item $_.fullname}
& {{ _alias.winss_svscan }} {{ dir }}\init
exit $LastExitCode
