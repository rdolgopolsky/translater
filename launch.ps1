param([string]$Python)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python-runtime.ps1')
$pythonExecutable = Resolve-TranslatorPython -Python $Python

Push-Location $PSScriptRoot
try {
    & $pythonExecutable -c 'import anthropic, customtkinter, google.genai, pyautogui, pyperclip, win32crypt, PIL, pystray, lingua'
    if ($LASTEXITCODE -ne 0) {
        throw 'Run setup.ps1 to install the project dependencies.'
    }
    $pythonw = Join-Path (Split-Path -Parent $pythonExecutable) 'pythonw.exe'
    if (-not (Test-Path -LiteralPath $pythonw)) {
        $pythonw = $pythonExecutable
    }
    Start-Process -FilePath $pythonw -ArgumentList ('"{0}"' -f (Join-Path $PSScriptRoot 'translator.py')) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
} finally {
    Pop-Location
}
