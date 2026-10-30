function Resolve-TranslatorPython {
    param([string]$Python)

    if ($Python) {
        $candidate = $Python
        $arguments = @()
    } elseif (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')) {
        $candidate = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
        $arguments = @()
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $candidate = 'py'
        $arguments = @('-3')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $candidate = 'python'
        $arguments = @()
    } else {
        throw 'Install Python 3.14 for Windows first. See README_TRANSFER.md.'
    }

    $resolved = & $candidate @arguments -c 'import sys; print(sys.executable)'
    if ($LASTEXITCODE -ne 0 -or -not $resolved -or -not (Test-Path -LiteralPath $resolved)) {
        throw 'Python is unavailable. Install Python 3.14 for Windows. See README_TRANSFER.md.'
    }
    return $resolved
}
