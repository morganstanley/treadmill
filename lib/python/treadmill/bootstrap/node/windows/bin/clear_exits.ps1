Get-ChildItem -Recurse "{{ dir }}\init\*\data\exits\*" | foreach ($_) {remove-item $_.fullname}
