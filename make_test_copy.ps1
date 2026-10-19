<#
Copie de test HORS LIGNE de Blur, avec un mod posé en fichiers en clair.

Par défaut : SIMULATION (affiche ce qui serait fait, ne touche à rien).
  .\make_test_copy.ps1                 simulation
  .\make_test_copy.ps1 -Run            crée la copie + sauvegarde ta sauvegarde Blur
  .\make_test_copy.ps1 -Restore -Run   remet ta sauvegarde Blur d'avant le test

Ce que fait -Run :
  1. vérifie : jeu source présent, Blur pas lancé, destination hors du dossier du jeu, place libre ;
  2. sauvegarde %APPDATA%\bizarre creations\blur\save + settings.xml dans Jeux_WII\blur_save_backups\<date>
     (la sauvegarde est PARTAGÉE entre toutes les installations : la copie de test écrit dedans) ;
  3. copie le jeu SANS AMAX (pas de d3d9.dll, pas de dossier amax\ : la copie ne peut pas aller en ligne)
     et sans nos fichiers de travail (Blur_debug.exe, *.py, CLAUDE.md, journaux) ;
  4. pose les fichiers du mod (chemins du jeu ; un fichier en clair passe avant le pak) ;
  5. écrit COPIE_DE_TEST_HORS_LIGNE.txt dans la copie.
Le jeu installé n'est jamais modifié (il n'est que lu).
#>
param(
    [string]$Source = "C:\Program Files (x86)\Activision\Blur(TM)",
    [string]$Dest   = "C:\Users\sanqu\Jeux_WII\Blur_test",
    [string]$Mod    = "C:\Users\sanqu\Jeux_WII\blur_extracted\mods\haruna_reverse\files",
    [string]$Backups = "C:\Users\sanqu\Jeux_WII\blur_save_backups",
    [switch]$Run,
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
if (Test-Path $dst) { throw "$dst existe déjà : supprime-le ou choisis un autre -Dest." }
if (-not (Test-Path $Mod)) { throw "Fichiers du mod introuvables : $Mod" }
$freeGB = [math]::Round((Get-PSDrive ($dst.Substring(0, 1))).Free / 1GB, 1)
if ($freeGB -lt 10) { throw "Pas assez de place ($freeGB Go libres, il en faut ~8)." }
Write-Host "Source  : $src"
Write-Host "Copie   : $dst   ($freeGB Go libres)"

# 2. save backup
$stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$bk = Join-Path $Backups $stamp
Write-Host "Sauvegarde Blur : $SaveDir\save + settings.xml  ->  $bk"
if ($Run) {
    New-Item -ItemType Directory -Path (Join-Path $bk "save") -Force | Out-Null
    Copy-Item (Join-Path $SaveDir "save\*") (Join-Path $bk "save") -Force
    Copy-Item (Join-Path $SaveDir "settings.xml") $bk -Force
}

# 3. copy without AMAX and without our work files
$excludeDirs  = @((Join-Path $src "amax"))
$excludeFiles = @("d3d9.dll", "d3d9.dll.test", "Blur_debug.exe", "*.py", "CLAUDE.md", "blur_rpc.log", "debug_event.dat")
Write-Host "Copie du jeu sans : amax\ ; $($excludeFiles -join ', ')"
$rc = @($src, $dst, "/E", "/R:1", "/W:1", "/NFL", "/NDL", "/NP", "/XD") + $excludeDirs + @("/XF") + $excludeFiles
if (-not $Run) { $rc += "/L" }                         # /L = list only
& robocopy @rc | Select-Object -Last 12
if ($LASTEXITCODE -ge 8) { throw "robocopy a échoué (code $LASTEXITCODE)" }

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

# 5. marker
if ($Run) {
    @"
Copie de TEST hors ligne de Blur (créée le $stamp par make_test_copy.ps1).
Sans AMAX : ne peut pas aller en ligne. Mod : $Mod
Sauvegarde Blur d'avant le test : $bk
Après le test : .\make_test_copy.ps1 -Restore -Run
"@ | Set-Content (Join-Path $dst "COPIE_DE_TEST_HORS_LIGNE.txt") -Encoding utf8
    if (Test-Path (Join-Path $dst "d3d9.dll")) { throw "d3d9.dll présent dans la copie : AMAX n'est pas retiré !" }
    Write-Host "`nPrêt. Lancer : $dst\Blur.exe   (après le test : -Restore -Run pour remettre ta sauvegarde)"
}
