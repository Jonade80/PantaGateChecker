from PyInstaller.utils.hooks import collect_submodules


analysis = Analysis(
    ["src/panta_gate_checker/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("assets/PantaGateChecker.ico", "."),
        ("assets/prometheus-panta.webp", "."),
    ],
    hiddenimports=collect_submodules("ntt_proto"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=0,
)
python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="PantaGateChecker",
    icon="assets/PantaGateChecker.ico",
    version="build/version_info.txt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)