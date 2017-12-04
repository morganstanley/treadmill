$runtime = '{{ treadmill_runtime }}'

if ($runtime -ne 'docker') {
    Write-Host 'Runtime is not docker - exiting'
    exit 0
}

if (!(Get-Command 'docker' -ErrorAction SilentlyContinue)) {
    Write-Host 'Docker command not found - exiting'
    exit 1
}

$containers = & docker ps -a -q

if ($containers) {
    Write-Host 'Stopping docker containers'
    & docker stop $containers

    Write-Host 'All docker containers have been stopped'
} else {
    Write-Host 'There were no docker containers to stop'
}
