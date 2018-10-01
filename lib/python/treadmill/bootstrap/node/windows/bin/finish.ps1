param (
    [int]$limit = 5,
    [int]$interval = 60,
    [string]$tombstone_path = $null,
    [string]$tombstone_id = $null,
    [string]$skip_path = $null,
    [switch]$ignore_exitinfo = $false
)

if (!$tombstone_path -or !$tombstone_id) {
    exit 0
}

if ($skip_path -and (Test-Path -PathType Any $skip_path)) {
    exit 0
}

# get exit info
$rc = [int] $env:SUPERVISE_RUN_EXIT_CODE
if ($rc -eq $null) {
    $rc = 0
}
$now = ([DateTime]::UtcNow - [DateTime]::new(1970, 1, 1, 0, 0, 0, 0, 'Utc')).TotalSeconds
$exit_info = '{0:0000000000},{1:000},000' -f $now, $rc

# append info to data\exits\log and keep the last $limit number of record
if ($limit -gt 0) {
    New-Item -ItemType Directory -Force -Path 'data\exits' | Out-Null

    Add-Content 'data\exits\log' $exit_info

    $all_exits = Get-Content 'data\exits\log'

    if ($all_exits.Count -le $limit) {
        exit 0
    }

    $last = $all_exits[0].Split(',')[0] -as [int]

    $all_exits = $all_exits | Select -Last $limit
    Set-Content 'data\exits\log' $all_exits

    if (($now - $last) -gt $interval) {
        exit 0
    }
    $exit_info = $all_exits[0]
}

if ($ignore_exitinfo) {
    $tombstone_file = '{0}\{1}' -f $tombstone_path, $tombstone_id
} else {
    $tombstone_file = '{0}\{1},{2}' -f $tombstone_path, $tombstone_id, $exit_info
}
New-Item $tombstone_file -force -type file | Out-Null
exit 125
