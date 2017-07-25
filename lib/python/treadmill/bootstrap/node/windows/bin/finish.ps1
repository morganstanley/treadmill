New-Item -ItemType Directory -Force -Path "data\exits" | Out-Null

$rc = [int] $env:SUPERVISE_RUN_EXIT_CODE
if ($rc -eq $null) {
    $rc = 0
}
$now = ([DateTime]::UtcNow - [DateTime]::new(1970, 1, 1, 0, 0, 0, 0, 'Utc')).TotalSeconds

$exit_file = "{0:0000000000.000},{1:000},000" -f $now, $rc
echo $null >> "data\exits\$exit_file"
exit 125
