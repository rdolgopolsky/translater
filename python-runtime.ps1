function Resolve-TranslatorPython {
    param([string]$Python, [switch]$SkipVirtualEnvironment)

    if ($Python) {
        $candidate = $Python
        $arguments = @()
    } elseif (-not $SkipVirtualEnvironment -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'))) {
        $candidate = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
        $arguments = @()
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $candidate = 'py'
        $arguments = @('-3.14')
    } elseif (Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe')) {
        $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'
        $arguments = @()
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $candidate = 'python'
        $arguments = @()
    } else {
        throw 'Install Python 3.14 for Windows first. See README_TRANSFER.md.'
    }

    $resolved = & $candidate @arguments -c 'import sys; assert sys.version_info[:2] == (3, 14); print(sys.executable)'
    if ($LASTEXITCODE -ne 0 -or -not $resolved -or -not (Test-Path -LiteralPath $resolved)) {
        throw 'Python 3.14 is unavailable or .venv was moved from another PC. Run setup.ps1 with a working Python 3.14. See README_TRANSFER.md.'
    }
    return $resolved
}
