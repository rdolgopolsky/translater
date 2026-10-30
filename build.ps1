param([string]$Python)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python-runtime.ps1')
$pythonExecutable = Resolve-TranslatorPython -Python $Python

Push-Location $PSScriptRoot
try {
    & $pythonExecutable -c 'import customtkinter, PyInstaller'
    if ($LASTEXITCODE -ne 0) {
        throw 'Install dependencies first: python -m pip install -r requirements.txt (use the Python from your .venv if present).'
    }
    & $pythonExecutable -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot 'Translator.spec')
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
    Write-Host ('Built: ' + (Join-Path $PSScriptRoot 'dist\Translator.exe'))
} finally {
    Pop-Location
}
