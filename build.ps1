param([string]$Python)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python-runtime.ps1')
$pythonExecutable = Resolve-TranslatorPython -Python $Python

Push-Location $PSScriptRoot
try {
    & $pythonExecutable -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed. Run setup.ps1.' }
    & $pythonExecutable -c 'import anthropic, customtkinter, google.genai, pyautogui, pyperclip, pynput, win32crypt, win32api, win32con, win32gui, win32process, PIL, pystray, PyInstaller, tzdata'
    if ($LASTEXITCODE -ne 0) {
        throw 'Run setup.ps1 to install the project dependencies.'
    }
    & $pythonExecutable -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot 'Translator.spec')
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
    Write-Host ('Built: ' + (Join-Path $PSScriptRoot 'dist\Translator.exe'))
} finally {
    Pop-Location
}
