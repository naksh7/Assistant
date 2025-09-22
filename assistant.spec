# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Data files to include
added_files = [
    ('config/settings.json', 'config'),
    ('config/commands.json', 'config'),
    ('resources/icon.ico', 'resources'),
    ('resources/icon.png', 'resources'),
    ('resources/readme.md', 'resources')
]

# Hidden imports for dependencies (keep third-party modules only)
hiddenimports = [
    'speech_recognition',
    'pyaudio',
    'psutil',
    'pyautogui',
    'PIL'
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico',
)
