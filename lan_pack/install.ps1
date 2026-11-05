# Blur Reverse LAN pack: install / uninstall, reversible.
# The pack folder goes inside the Blur folder (next to Blur.exe). Install backs up every file it replaces
# (pack_backup\) and lists the files it adds (pack_backup\added.txt); uninstall puts everything back.
param([switch]$Uninstall)
$ErrorActionPreference = "Stop"
$pack = $PSScriptRoot
$game = Split-Path $pack -Parent
$files = Join-Path $pack "files"
$backup = Join-Path $pack "pack_backup"
$plugins = Join-Path $game "amax\plugins\plugins.lua"
$requires = @('require("ai19.ai19"),')

if (-not (Test-Path (Join-Path $game "Blur.exe"))) { throw "Blur.exe introuvable dans $game : mets ce dossier dans le dossier de Blur." }
if (Get-Process -Name "Blur" -ErrorAction SilentlyContinue) { throw "Ferme Blur avant de continuer." }

if ($Uninstall) {
    if (-not (Test-Path $backup)) { throw "Pack non installé (pas de pack_backup)." }
    Get-Content (Join-Path $backup "added.txt") | Where-Object { $_ } | ForEach-Object {
        $p = Join-Path $game $_
        if (Test-Path $p) { Remove-Item $p -Force }
    }
    Get-ChildItem $backup -Recurse -File | Where-Object { $_.Name -ne "added.txt" } | ForEach-Object {
        $rel = $_.FullName.Substring($backup.Length + 1)
        $dst = Join-Path $game $rel
        New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
        Copy-Item $_.FullName $dst -Force
    }
    # folders the pack created and left empty
    $dirs = Get-Content (Join-Path $backup "added.txt") | Where-Object { $_ } | ForEach-Object {
        $d = Split-Path (Join-Path $game $_)
        while ($d.Length -gt $game.Length) { $d; $d = Split-Path $d }
    }
    $dirs | Sort-Object -Unique | Sort-Object Length -Descending |
        Where-Object { (Test-Path $_) -and -not (Get-ChildItem $_ -Recurse -File) } | ForEach-Object { Remove-Item $_ -Recurse -Force }
    Remove-Item $backup -Recurse -Force
    Write-Host "Pack désinstallé : le jeu est revenu comme avant."
    exit 0
}

if (Test-Path $backup) { throw "Pack déjà installé : désinstalle d'abord." }
New-Item -ItemType Directory -Force $backup | Out-Null
$addedList = Join-Path $backup "added.txt"
New-Item -ItemType File -Force $addedList | Out-Null        # written as we go: an interrupted install can still be undone
Get-ChildItem $files -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($files.Length + 1)
    $dst = Join-Path $game $rel
    if (Test-Path $dst) {
        $b = Join-Path $backup $rel
        New-Item -ItemType Directory -Force (Split-Path $b) | Out-Null
        Copy-Item $dst $b -Force
        Set-ItemProperty $dst -Name IsReadOnly -Value $false
    } else { Add-Content $addedList $rel }
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    Copy-Item $_.FullName $dst -Force
}
# plugins.lua: the player's own list, plus our require lines (never replaced)
$b = Join-Path $backup "amax\plugins\plugins.lua"
New-Item -ItemType Directory -Force (Split-Path $b) | Out-Null
Copy-Item $plugins $b -Force
Set-ItemProperty $plugins -Name IsReadOnly -Value $false
$lua = Get-Content $plugins -Raw
foreach ($r in $requires) {
    if ($lua -notmatch [regex]::Escape($r.TrimEnd(','))) { $lua = $lua -replace '\}\s*$', "`t$r`n}`n" }
}
Set-Content $plugins $lua -NoNewline -Encoding UTF8
Write-Host "Pack installé : $((Get-Content $addedList).Count) fichiers ajoutés, $((Get-ChildItem $backup -Recurse -File).Count - 1) sauvegardés."
