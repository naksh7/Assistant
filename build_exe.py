#!/usr/bin/env python3
"""
Build script for Assistant 
Creates a standalone executable using PyInstaller
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def clean_build_dirs():
    """Clean previous build directories"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}...")
            shutil.rmtree(dir_name)
            
    # Clean pycache in subdirectories
    for root, dirs, files in os.walk('.'):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                pycache_path = os.path.join(root, dir_name)
                print(f"Cleaning {pycache_path}...")
                shutil.rmtree(pycache_path)

def create_spec_file():
    """Create PyInstaller spec file"""
    # If a PNG icon exists but no ICO, attempt to convert it to a multi-size .ico
    try:
        from PIL import Image
        png_path = Path('resources') / 'icon.png'
        ico_path = Path('resources') / 'icon.ico'
        if png_path.exists() and not ico_path.exists():
            print('Converting resources/icon.png -> resources/icon.ico')
            try:
                im = Image.open(png_path)
                # Save multiple sizes for compatibility
                sizes = [(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)]
                im.save(ico_path, format='ICO', sizes=sizes)
                print('Icon converted successfully')
            except Exception as e:
                print(f'Icon conversion failed: {e}')
    except Exception:
        # Pillow not available or conversion failed; proceed and hope .ico exists
        pass

    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

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
'''
    
    with open('assistant.spec', 'w') as f:
        f.write(spec_content)
    print("Created assistant.spec file")

def build_executable():
    """Build the executable using PyInstaller"""
    try:
        print("Building executable...")
        
        # Build using the spec file
        result = subprocess.run([
            sys.executable, '-m', 'PyInstaller',
            '--clean',
            '--noconfirm',
            'assistant.spec'
        ], check=True, capture_output=True, text=True)
        
        print("Build output:")
        print(result.stdout)
        if result.stderr:
            print("Build warnings/errors:")
            print(result.stderr)
            
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        print(f"Error output: {e.stderr}")
        return False

def post_build_cleanup():
    """Clean up after build"""
    print("Performing post-build cleanup...")
    
    # Check if exe was created
    exe_path = Path('dist/Assistant.exe')
    if exe_path.exists():
        print(f"✓ Executable created successfully: {exe_path}")
        print(f"  File size: {exe_path.stat().st_size / (1024*1024):.1f} MB")        
        return True
    else:
        print("✗ Executable was not created")
        return False

def main():
    """Main build process"""
    print("=" * 50)
    print("Building Assistant Executable")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path('main.py').exists():
        print("Error: main.py not found. Please run this script from the project root.")
        sys.exit(1)
    
    # Check if resources and config exist
    resources_dir = Path('resources')
    config_dir = Path('config')
    if not resources_dir.exists():
        print("Error: resources directory not found")
        sys.exit(1)
    
    if not config_dir.exists():
        print("Error: config directory not found")
        sys.exit(1)
    
    # Check for required config files
    required_config_files = ['settings.json', 'commands.json']
    for config_file in required_config_files:
        if not (config_dir / config_file).exists():
            print(f"Error: {config_file} not found in config directory")
            sys.exit(1)
    
    try:
        # Step 1: Clean previous builds
        print("Step 1: Cleaning previous builds...")
        clean_build_dirs()
        
        # Step 2: Create spec file
        print("Step 2: Creating PyInstaller spec file...")
        create_spec_file()
        
        # Step 3: Build executable
        print("Step 3: Building executable...")
        if not build_executable():
            print("Build failed!")
            sys.exit(1)
        
        # Step 4: Post-build cleanup
        print("Step 4: Post-build cleanup...")
        if post_build_cleanup():
            print("\n" + "=" * 50)
            print("BUILD SUCCESSFUL!")
            print("=" * 50)
            print("Your executable is ready:")
            print("  • Main executable: release/Assistant.exe")
            print("  • You can distribute the entire 'release' folder")
            print("  • Or just the Assistant.exe if you prefer a single file")
        else:
            print("Build completed but post-processing failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"Build process failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
