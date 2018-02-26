param (
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$monitor_service = $null
)

Write-Host 'Received SIGTERM'

if ($monitor_servicee) {
    {{ _alias.winss_svc }} -k -wD $monitor_service
}

# SIGTERM : acts as if a winss-svscanctl -q command had been received.
{{ _alias.winss_svscanctl }} -q .
