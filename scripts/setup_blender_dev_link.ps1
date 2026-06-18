$ErrorActionPreference = "Stop"

param(
    [string]$BlenderVersion = "5.1"
)

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$addonSource = Join-Path $repoRoot "busy_layout_mvp"
$addonsDir = Join-Path $env:APPDATA "Blender Foundation\Blender\$BlenderVersion\scripts\addons"
$addonLink = Join-Path $addonsDir "busy_layout_mvp"

if (!(Test-Path -LiteralPath $addonSource)) {
    throw "Cannot find add-on source folder: $addonSource"
}

New-Item -ItemType Directory -Path $addonsDir -Force | Out-Null

Get-ChildItem -LiteralPath $addonsDir -Force -Filter "busy_layout_mvp_v*.py" | ForEach-Object {
    $backupPath = $_.FullName + ".disabled-backup"
    if (Test-Path -LiteralPath $backupPath) {
        Remove-Item -LiteralPath $backupPath -Force
    }
    Move-Item -LiteralPath $_.FullName -Destination $backupPath
}

if (Test-Path -LiteralPath $addonLink) {
    $existing = Get-Item -LiteralPath $addonLink -Force
    if ($existing.LinkType -eq "Junction" -or $existing.LinkType -eq "SymbolicLink") {
        Remove-Item -LiteralPath $addonLink -Force
    } else {
        throw "Path already exists and is not a link: $addonLink"
    }
}

New-Item -ItemType Junction -Path $addonLink -Target $addonSource | Out-Null

Write-Host "Busy Layout dev link installed:"
Write-Host "  $addonLink"
Write-Host "  -> $addonSource"
Write-Host ""
Write-Host "Restart Blender, then enable the 'Busy Layout MVP' add-on module named busy_layout_mvp."
