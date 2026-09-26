<#
.SYNOPSIS
    Vytvoří virtuální prostředí, nainstaluje závislosti a sestaví jednosouborové
    RosDownloader.exe pomocí PyInstalleru.

.DESCRIPTION
    Spusť z kořene projektu:

        powershell -ExecutionPolicy Bypass -File .\build.ps1

    Parametry:
        -Python <cesta>   konkrétní interpret (jinak se hledá py -3.14 / -3.13 / -3.12)
        -Clean            smaže .venv, build a dist a začne od nuly
        -SkipTests        přeskočí pytest (ve výchozím stavu se testy pustí)
        -Console          sestaví konzolovou variantu (kvůli ladění)

.NOTES
    Nepoužívej Python z Microsoft Storu – PyInstaller se nedostane k jeho
    souborům v C:\Program Files\WindowsApps a build selže.
#>

[CmdletBinding()]
param(
    [string]$Python = "",
    [switch]$Clean,
    [switch]$SkipTests,
    [switch]$Console
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$AppName = "RosDownloader"
$VenvDir = Join-Path $PSScriptRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$IconPath = Join-Path $PSScriptRoot "assets\rosdl.ico"

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Fail([string]$Text) {
    Write-Host "CHYBA: $Text" -ForegroundColor Red
    exit 1
}

# --------------------------------------------------------------------------- #
# 1. Interpret
# --------------------------------------------------------------------------- #
function Resolve-Python {
    if ($Python) {
        if (-not (Test-Path $Python)) { Fail "Zadaný Python neexistuje: $Python" }
        return $Python
    }
    foreach ($version in @("3.14", "3.13", "3.12")) {
        $found = & py "-$version" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $found) { return $found.Trim() }
    }
    $fallback = (Get-Command python -ErrorAction SilentlyContinue)
    if ($fallback) { return $fallback.Source }
    Fail "Nenašel jsem Python 3.12+. Nainstaluj ho z python.org."
}

Write-Step "Hledám Python"
$PythonExe = Resolve-Python
Write-Host "    $PythonExe"

if ($PythonExe -like "*WindowsApps*") {
    Fail @"
Tohle je Python z Microsoft Storu ($PythonExe).
PyInstaller s ním neumí sestavit .exe – nedostane se k souborům
v C:\Program Files\WindowsApps kvůli oprávněním.
Nainstaluj Python z python.org a spusť build znovu, případně předej
cestu ručně: .\build.ps1 -Python C:\Python312\python.exe
"@
}

$versionText = & $PythonExe -c "import sys; print('%d.%d' % sys.version_info[:2])"
Write-Host "    verze $versionText"

# --------------------------------------------------------------------------- #
# 2. Úklid a virtuální prostředí
# --------------------------------------------------------------------------- #
if ($Clean) {
    Write-Step "Úklid"
    foreach ($dir in @($VenvDir, "build", "dist")) {
        if (Test-Path $dir) {
            Write-Host "    mažu $dir"
            Remove-Item -Recurse -Force $dir
        }
    }
    Get-ChildItem -Filter "*.spec" | Remove-Item -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $VenvPython)) {
    Write-Step "Vytvářím virtuální prostředí (.venv)"
    & $PythonExe -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Fail "Nepodařilo se vytvořit .venv" }
}

Write-Step "Instaluji závislosti"
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install --quiet -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { Fail "Instalace závislostí selhala" }

# --------------------------------------------------------------------------- #
# 3. Testy
# --------------------------------------------------------------------------- #
if (-not $SkipTests) {
    Write-Step "Pouštím testy"
    & $VenvPython -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { Fail "Testy neprošly – build zastaven" }
}

# --------------------------------------------------------------------------- #
# 4. Ikona
# --------------------------------------------------------------------------- #
if (-not (Test-Path $IconPath)) {
    Write-Step "Generuji ikonu"
    & $VenvPython tools\make_icon.py
    if ($LASTEXITCODE -ne 0) { Fail "Ikonu se nepodařilo vytvořit" }
}

# --------------------------------------------------------------------------- #
# 5. PyInstaller
# --------------------------------------------------------------------------- #
Write-Step "Sestavuji $AppName.exe"

$windowMode = if ($Console) { "--console" } else { "--windowed" }

$arguments = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    $windowMode,
    "--name", $AppName,
    "--icon", $IconPath,
    # Ikona musí být i uvnitř .exe – používá ji okno a hlavní panel.
    "--add-data", "$IconPath;assets",
    # Qt moduly, které PySide6 táhne s sebou, ale aplikace je nepotřebuje.
    "--exclude-module", "PySide6.QtQml",
    "--exclude-module", "PySide6.QtQuick",
    "--exclude-module", "PySide6.Qt3DCore",
    "--exclude-module", "PySide6.QtWebEngineCore",
    "--exclude-module", "PySide6.QtMultimedia",
    "--exclude-module", "PySide6.QtCharts",
    "--exclude-module", "PySide6.QtDataVisualization",
    "--exclude-module", "tkinter",
    "--exclude-module", "unittest",
    "--exclude-module", "pytest",
    "main.py"
)

& $VenvPython -m PyInstaller @arguments
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller skončil chybou" }

# --------------------------------------------------------------------------- #
# 6. Výsledek
# --------------------------------------------------------------------------- #
$exe = Join-Path $PSScriptRoot "dist\$AppName.exe"
if (-not (Test-Path $exe)) { Fail "Výsledný .exe nevznikl" }

$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Step "Hotovo"
Write-Host "    $exe" -ForegroundColor Green
Write-Host "    velikost $sizeMb MB"
Write-Host ""
Write-Host "    Aplikace nepotřebuje nainstalovaný Python." -ForegroundColor Green
Write-Host "    Nastavení a cache si ukládá do %APPDATA%\$AppName\."
