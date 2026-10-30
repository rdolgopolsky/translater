param([string]$Python)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python-runtime.ps1')
$pythonExecutable = Resolve-TranslatorPython -Python $Python -SkipVirtualEnvironment
$venvPath = Join-Path $PSScriptRoot '.venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'

if (Test-Path -LiteralPath $venvPath) {
    $usable = $false
    if (Test-Path -LiteralPath $venvPython) {
        try {
            & $venvPython -c 'import sys; assert sys.version_info[:2] == (3, 14)' 2>$null
            $usable = $LASTEXITCODE -eq 0
        } catch { $usable = $false }
    }
    if (-not $usable) {
        # Preserve the previous environment instead of deleting it.
        $backupPath = Join-Path $PSScriptRoot ('.venv.backup-' + [guid]::NewGuid().ToString('N'))
        if ((Split-Path -Parent ([IO.Path]::GetFullPath($venvPath))) -ne $PSScriptRoot) {
            throw 'Environment path must be inside the project.'
        }
        Move-Item -LiteralPath $venvPath -Destination $backupPath
        Write-Host ('Previous environment preserved: ' + $backupPath)
    }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    & $pythonExecutable -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv.' }
}
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not update pip.' }
& $venvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not install dependencies.' }
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
& $venvPython -c 'import anthropic, customtkinter, google.genai, pyautogui, pyperclip, pynput, win32crypt, win32api, win32con, win32gui, win32process, PIL, pystray, PyInstaller; from zoneinfo import ZoneInfo; ZoneInfo(''America/Los_Angeles'')'
if ($LASTEXITCODE -ne 0) { throw 'Environment check failed.' }
Write-Host 'Ready. Launch: .\Translator.cmd   Build: powershell -ExecutionPolicy Bypass -File .\build.ps1'
