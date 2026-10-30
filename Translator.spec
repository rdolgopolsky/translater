# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import customtkinter
from PyInstaller.utils.hooks import collect_data_files

project_dir = Path(SPECPATH)
icon_path = str(Path(customtkinter.__file__).parent / 'assets' / 'icons' / 'CustomTkinter_icon_Windows.ico')

a = Analysis(
    [str(project_dir / 'translator.py')],
    pathex=[],
    binaries=[],
    datas=collect_data_files('customtkinter') + collect_data_files('tzdata'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Translator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[icon_path],
)
