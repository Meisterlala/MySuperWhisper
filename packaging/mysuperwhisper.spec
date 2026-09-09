# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the macOS MySuperWhisper.app bundle.
#
# Build from the project root with:
#   venv/bin/pyinstaller packaging/mysuperwhisper.spec --noconfirm
#
# Heavy ML deps (torch/transformers/accelerate/etc.) don't always get fully
# picked up by PyInstaller's static import scan, so they're pulled in
# explicitly via collect_all below.

import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

PROJECT_ROOT = os.path.dirname(SPECPATH)

COLLECT_ALL_PACKAGES = [
    "torch",
    "torchaudio",
    "transformers",
    "accelerate",
    "huggingface_hub",
    "safetensors",
    "tokenizers",
    "soundfile",
    "sounddevice",
    "pynput",
    "pystray",
    "PIL",
    "AppKit",
    "Quartz",
    "Foundation",
    "objc",
]

datas = []
binaries = []
hiddenimports = []

for pkg in COLLECT_ALL_PACKAGES:
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    [os.path.join(SPECPATH, "entrypoint.py")],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MySuperWhisper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MySuperWhisper",
)

app = BUNDLE(
    coll,
    name="MySuperWhisper.app",
    icon=os.path.join(SPECPATH, "MySuperWhisper.icns"),
    bundle_identifier="com.local.mysuperwhisper",
    version="1.6.1",
    info_plist={
        "CFBundleName": "MySuperWhisper",
        "CFBundleDisplayName": "MySuperWhisper",
        "CFBundleShortVersionString": "1.6.1",
        "LSUIElement": True,
        "NSMicrophoneUsageDescription": "MySuperWhisper needs microphone access to record audio for transcription.",
        "NSAppleEventsUsageDescription": "MySuperWhisper needs to send keystrokes to paste transcribed text into other apps.",
    },
)
