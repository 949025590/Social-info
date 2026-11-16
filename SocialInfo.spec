import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("playwright")
tray_data, tray_binaries, tray_hidden = collect_all("pystray")
datas += tray_data
binaries += tray_binaries
hiddenimports += tray_hidden
for name in ("ffi-8.dll", "liblzma.dll", "libbz2.dll", "libexpat.dll", "tcl86t.dll", "tk86t.dll"):
    dll = Path(sys.executable).parent / "Library" / "bin" / name
    if dll.exists():
        binaries.append((str(dll), "."))

a = Analysis(
    ["src/social_info/entry.py"], pathex=["src"], binaries=binaries,
    datas=datas, hiddenimports=hiddenimports, excludes=["pytest"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="SocialInfo",
    console=False, icon="assets/icon.ico", disable_windowed_traceback=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=False, name="SocialInfo",
)
