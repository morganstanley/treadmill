& {{ dir }}\bin\docker_reset.ps1

foreach ($dir in @('init', 'init1')) {
    Get-ChildItem "{{ dir }}\$dir" | Where-Object {!$_.Name.StartsWith('.')} | foreach ($_) {
        if (!(Get-Content "{{ dir }}\.install" | Select-String -Quiet -Pattern "C:\\treadmill\\$dir\\$($_.Name)\\$")) {
            Write-Host "Removing extra service: $($_.FullName)"
            Remove-Item $_.FullName -Recurse
        }
    }

    Get-ChildItem -Recurse "{{ dir }}\$dir\*\data\exits\*" | foreach ($_) {
        Remove-Item $_.FullName
    }
}

Get-ChildItem "{{ dir }}\watchdogs\*" | Where-Object {!$_.Name.StartsWith('.')} | foreach ($_) {
    Remove-Item $_.FullName
}

Get-ChildItem "{{ dir }}\running\*" | Where-Object {!$_.Name.StartsWith('.')} | foreach ($_) {
    Write-Host "Removing running symlink: $($_.FullName)"
    & cmd /c rmdir $_.FullName
}

Get-ChildItem "{{ dir }}\cleanup\*" | Where-Object {!$_.Name.StartsWith('.')} | foreach ($_) {
    Write-Host "Removing cleanup symlink: $($_.FullName)"
    & cmd /c rmdir $_.FullName
}

Get-ChildItem "{{ dir }}\cleaning\*" | Where-Object {!$_.Name.StartsWith('.')} | foreach ($_) {
    Write-Host "Removing cleaning symlink: $($_.FullName)"
    & cmd /c rmdir $_.FullName
}

Get-ChildItem "{{ dir }}\tombstones\*\*" | Where-Object {!$_.Name.StartsWith('.')} | foreach ($_) {
    Remove-Item $_.FullName
}

& {{ _alias.winss_svscan }} {{ dir }}\init
exit $LastExitCode
