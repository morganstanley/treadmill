param (
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$services = @('monitor')
)

Write-Host 'Received SIGTERM'

foreach ($service in $services) {
    if (Test-Path -Path monitor) {
        {{ _alias.winss_svc }} -k -wD monitor
    }
}

# SIGTERM : acts as if a winss-svscanctl -q command had been received.
{{ _alias.winss_svscanctl }} -q .
