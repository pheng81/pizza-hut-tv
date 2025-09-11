param(
    [string]$StoreId = "1000",
    [string]$PairCode = "1340"
)

$ErrorActionPreference = 'Stop'
$headers = @{ 'X-User-Code' = $PairCode }
$rows = @()

foreach ($i in 1..9) {
    $sid = "screen$($i)"
    try {
        $u = "https://api.everydayadvertise.com/playlist/$StoreId/$sid"
        $r = Invoke-RestMethod -Headers $headers -Uri $u -Method Get -TimeoutSec 20
        $count = if ($r.playlist) { $r.playlist.Count } else { 0 }
        $syncCount = if ($r.playlist) { ($r.playlist | Where-Object { $_.sync_ref -ne $null }).Count } else { 0 }
        $firstKinds = @()
        if ($r.playlist) {
            $firstKinds = ($r.playlist | Select-Object -First 3 | ForEach-Object { $_.kind }) -join ','
        }
        $rows += [PSCustomObject]@{ screen = $sid; count = $count; sync = $syncCount; kinds = $firstKinds }
    }
    catch {
        $rows += [PSCustomObject]@{ screen = $sid; count = $null; sync = $null; kinds = $null }
    }
}

$rows | Sort-Object screen | Format-Table -AutoSize
$best = $rows | Where-Object { $_.sync -gt 0 } | Select-Object -First 1
if ($best) {
    Write-Host ("SYNC screen: $($best.screen)")
} else {
    Write-Host 'No sync screens found'
}
