# =============================================================================
#  MapleBot  -  Build to EXE
#  Usage:  .\build.ps1
#  Output: dist\MapleBot.exe
# =============================================================================

$ErrorActionPreference = Stop
$ProjectRoot = $PSScriptRoot

Write-Host "
Write-Host ============================================= -ForegroundColor Cyan
Write-Host   MapleBot  -  Build Script -ForegroundColor Cyan
Write-Host ============================================= -ForegroundColor Cyan
Write-Host 

# 1. Install dependencies
Write-Host [1/4] Installing / verifying dependencies... -ForegroundColor Yellow
pip install -r $ProjectRoot\requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { Write-Host ERROR: pip install failed. -ForegroundColor Red; exit 1 }
Write-Host       Done. -ForegroundColor Green

# 2. Clean old build artefacts
Write-Host [2/4] Cleaning previous build output... -ForegroundColor Yellow
foreach ($folder in @($ProjectRoot\build, $ProjectRoot\dist)) {
 if (Test-Path $folder) { Remove-Item $folder -Recurse -Force; Write-Host       Removed: $folder -ForegroundColor DarkGray }
}
if (Test-Path $ProjectRoot\MapleBot.spec) { Remove-Item $ProjectRoot\MapleBot.spec -Force }
Write-Host       Done. -ForegroundColor Green

# 3. Run PyInstaller
Write-Host [3/4] Compiling with PyInstaller... -ForegroundColor Yellow
Set-Location $ProjectRoot
pyinstaller main.py --onefile --windowed --name=MapleBot --clean `
 --hidden-import=pynput.keyboard._win32 `
 --hidden-import=pynput.mouse._win32 `
 --hidden-import=pynput._util.win32 `
 --hidden-import=win32api `
 --hidden-import=win32con `
 --hidden-import=win32gui `
 --hidden-import=win32process `
 --hidden-import=win32ui `
 --hidden-import=winerror `
 --hidden-import=pywintypes

if ($LASTEXITCODE -ne 0) { Write-Host ERROR: PyInstaller failed. -ForegroundColor Red; exit 1 }

# 4. Report
Write-Host 
Write-Host [4/4] Build complete! -ForegroundColor Green
$exePath = $ProjectRoot\dist\MapleBot.exe
if (Test-Path $exePath) {
 $sizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
 Write-Host 
 Write-Host   Output : $exePath -ForegroundColor Cyan
 Write-Host   Size   : $sizeMB MB -ForegroundColor Cyan
 Write-Host   Run    : .\dist\MapleBot.exe -ForegroundColor White
}
Write-Host 
Write-Host ============================================= -ForegroundColor Cyan
