$ErrorActionPreference = "Stop"

$python = "C:\Python314\python.exe"
$icon = "C:\Users\rdolg\AppData\Roaming\Python\Python314\site-packages\customtkinter\assets\icons\CustomTkinter_icon_Windows.ico"

if (-not (Test-Path $python)) {
    throw "Python 3.14 was not found at $python"
}
if (-not (Test-Path $icon)) {
    throw "Application icon was not found at $icon"
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --uac-admin `
    --name "Translator" `
    --icon $icon `
    --add-data "$icon;customtkinter/assets/icons" `
    translator.py

Write-Host "Built: dist\Translator.exe"
