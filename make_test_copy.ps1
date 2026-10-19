<#
Copie de test HORS LIGNE de Blur, avec un mod posé en fichiers en clair.

Par défaut : SIMULATION (affiche ce qui serait fait, ne touche à rien).
  .\make_test_copy.ps1                 simulation
  .\make_test_copy.ps1 -Run            crée la copie + sauvegarde ta sauvegarde Blur
  .\make_test_copy.ps1 -Update -Run    copie déjà faite : remet seulement AMAX hors ligne + les fichiers du mod
  .\make_test_copy.ps1 -Restore -Run   remet ta sauvegarde Blur d'avant le test

Ce que fait -Run :
  1. vérifie : jeu source présent, Blur pas lancé, destination hors du dossier du jeu, place libre ;
  2. sauvegarde %APPDATA%\bizarre creations\blur\save + settings.xml dans Jeux_WII\blur_save_backups\<date>
     (la sauvegarde est PARTAGÉE entre toutes les installations : la copie de test écrit dedans) ;
  3. copie le jeu avec AMAX HORS LIGNE : d3d9.dll + chargeur Lua + plugins (solo = course LAN seul, F1),
     mais SANS amax_auth.asi (connexion AMAX), amax_pfp.dll, blur_rpc.dll ni amax\config (redirection des
     serveurs) : la copie ne peut pas aller en ligne. Sans nos fichiers de travail (Blur_debug.exe, *.py...) ;
  4. pose les fichiers du mod (chemins du jeu ; un fichier en clair passe avant le pak) ;
  5. écrit COPIE_DE_TEST_HORS_LIGNE.txt dans la copie et vérifie qu'aucun module en ligne n'y est.
Le jeu installé n'est jamais modifié (il n'est que lu).
#>
param(
    [string]$Source = "C:\Program Files (x86)\Activision\Blur(TM)",
    [string]$Dest   = "C:\Users\sanqu\Jeux_WII\Blur_test",
    [string]$Mod    = "C:\Users\sanqu\Jeux_WII\blur_extracted\mods\haruna_reverse\files",
    [string]$Backups = "C:\Users\sanqu\Jeux_WII\blur_save_backups",
    [switch]$Run,
    [switch]$Update,
    [switch]$Restore
)
$ErrorActionPreference = "Stop"
$SaveDir  = Join-Path $env:APPDATA "bizarre creations\blur"
$mode = if ($Run) { "EXÉCUTION" } else { "SIMULATION (rien n'est modifié ; ajouter -Run)" }
Write-Host "== $mode"

if (Get-Process -Name "Blur", "Blur_debug" -ErrorAction SilentlyContinue) { throw "Blur est lancé : ferme-le d'abord." }

if ($Restore) {
    $last = Get-ChildItem $Backups -Directory -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
    if (-not $last) { throw "Aucune sauvegarde dans $Backups" }
    Write-Host "Remettre la sauvegarde $($last.FullName) dans $SaveDir"
    if ($Run) {
        Copy-Item (Join-Path $last.FullName "save\*") (Join-Path $SaveDir "save") -Force
        Copy-Item (Join-Path $last.FullName "settings.xml") $SaveDir -Force
        Write-Host "Sauvegarde remise."
    }
    return
}

# 1. checks
if (-not (Test-Path (Join-Path $Source "Blur.exe"))) { throw "Blur.exe introuvable dans $Source" }
$src = (Resolve-Path $Source).Path.TrimEnd('\')
$dst = [System.IO.Path]::GetFullPath($Dest).TrimEnd('\')
if ($dst -ieq $src -or $dst.StartsWith($src + "\", "OrdinalIgnoreCase")) { throw "La destination ne doit pas être dans le dossier du jeu." }
if ($Update) {
    if (-not (Test-Path (Join-Path $dst "COPIE_DE_TEST_HORS_LIGNE.txt"))) { throw "$dst n'est pas une copie de test." }
} elseif (Test-Path $dst) { throw "$dst existe déjà : supprime-le, choisis un autre -Dest, ou -Update." }
if (-not (Test-Path $Mod)) { throw "Fichiers du mod introuvables : $Mod" }
$freeGB = [math]::Round((Get-PSDrive ($dst.Substring(0, 1))).Free / 1GB, 1)
if (-not $Update -and $freeGB -lt 10) { throw "Pas assez de place ($freeGB Go libres, il en faut ~8)." }
Write-Host "Source  : $src"
Write-Host "Copie   : $dst   ($freeGB Go libres)"

# 2. save backup (not with -Update: the backup made before the first test must stay the latest one)
$stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$bk = Join-Path $Backups $stamp
if (-not $Update) {
    Write-Host "Sauvegarde Blur : $SaveDir\save + settings.xml  ->  $bk"
    if ($Run) {
        New-Item -ItemType Directory -Path (Join-Path $bk "save") -Force | Out-Null
        Copy-Item (Join-Path $SaveDir "save\*") (Join-Path $bk "save") -Force
        Copy-Item (Join-Path $SaveDir "settings.xml") $bk -Force
    }
}

# 3. copy with offline AMAX (Lua loader + plugins), without its online parts and without our work files
$excludeDirs  = @((Join-Path $src "amax\config"), (Join-Path $src "amax\log"))
$excludeFiles = @("amax_auth.asi", "amax_pfp.dll", "blur_rpc.dll", "d3d9.dll.test", "Blur_debug.exe", "*.py",
                  "CLAUDE.md", "blur_rpc.log", "debug_event.dat")
Write-Host "Copie sans : amax\config, amax\log ; $($excludeFiles -join ', ')"
$from, $to = $src, $dst
if ($Update) {                                          # only the AMAX part (+ d3d9.dll) of an existing copy
    $from, $to = (Join-Path $src "amax"), (Join-Path $dst "amax")
    Write-Host "Copie : d3d9.dll"
    if ($Run) { Copy-Item (Join-Path $src "d3d9.dll") $dst -Force }
}
$rc = @($from, $to, "/E", "/R:1", "/W:1", "/NFL", "/NDL", "/NP", "/XD") + $excludeDirs + @("/XF") + $excludeFiles
if (-not $Run) { $rc += "/L" }                         # /L = list only
& robocopy @rc | Select-Object -Last 12
if ($LASTEXITCODE -ge 8) { throw "robocopy a échoué (code $LASTEXITCODE)" }

# 3 bis. a pak wins over loose files (Process Monitor): lay the files of the paks the mod touches loose and set
# the paks aside. gamedata.pak (data) -> <copy>\gamedata ; root.pak (models, UI pictures...) -> <copy>\
$extracted = Split-Path $Mod -Parent | Split-Path -Parent | Split-Path -Parent
foreach ($u in @(@("gamedata", "gamedata\gamedata", "gamedata"), @("root", "root", ""))) {
    $pak, $from, $to = $u[0], (Join-Path $extracted $u[1]), (Join-Path $dst $u[2])
    Write-Host "$pak en clair : $from -> $to ; cache\$pak.pak (+ .sig) -> .off"
    if ($Run) {
        & robocopy $from $to /E /XC /XN /XO /NFL /NDL /NP /NJH /NJS | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy $pak a échoué (code $LASTEXITCODE)" }
        foreach ($f in "$pak.pak", "$pak.sig") {
            $p = Join-Path $dst "cache\$f"
            if (Test-Path $p) { Move-Item $p "$p.off" -Force }
        }
    }
}

# 4. mod files
Get-ChildItem $Mod -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring((Resolve-Path $Mod).Path.Length).TrimStart('\')
    Write-Host "Mod : $rel"
    if ($Run) {
        $target = Join-Path $dst $rel
        New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
        Copy-Item $_.FullName $target -Force
    }
}

# 5. marker + offline check
if ($Run) {
    if (-not $Update) {
        @"
Copie de TEST hors ligne de Blur (créée le $stamp par make_test_copy.ps1).
AMAX hors ligne (Lua + plugins, sans amax_auth.asi ni redirection des serveurs). Mod : $Mod
Sauvegarde Blur d'avant le test : $bk
Après le test : .\make_test_copy.ps1 -Restore -Run
"@ | Set-Content (Join-Path $dst "COPIE_DE_TEST_HORS_LIGNE.txt") -Encoding utf8
    }
    foreach ($bad in "amax\dlls\amax_auth.asi", "amax\dlls\amax_pfp.dll", "amax\dlls\blur_rpc.dll", "amax\config") {
        if (Test-Path (Join-Path $dst $bad)) { throw "$bad présent dans la copie : elle pourrait aller en ligne !" }
    }
    Write-Host "`nPrêt. Lancer : $dst\Blur.exe   (après le test : -Restore -Run pour remettre ta sauvegarde)"
}
