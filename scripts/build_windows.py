import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from social_info.icon import social_icon

ROOT = Path(__file__).parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-installer", action="store_true")
    args = parser.parse_args()
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    social_icon(256).save(assets / "icon.png")
    social_icon(256).save(assets / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "SocialInfo.spec"],
                   cwd=ROOT, check=True)
    cache = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
                                Path(os.environ["LOCALAPPDATA"]) / "ms-playwright"))
    target = ROOT / "dist" / "SocialInfo" / "browser"
    for source in cache.iterdir():
        if source.is_dir() and source.name.startswith(("chromium-", "chromium_headless_shell-", "ffmpeg-", "winldd-")):
            shutil.copytree(source, target / source.name, dirs_exist_ok=True)
    shutil.copytree(ROOT / "extension", ROOT / "dist" / "SocialInfo" / "extension", dirs_exist_ok=True)
    shutil.copytree(ROOT / "docs", ROOT / "dist" / "SocialInfo" / "docs", dirs_exist_ok=True)
    print(f"EXE 目录：{ROOT / 'dist' / 'SocialInfo'}")
    if args.no_installer:
        return
    iscc = shutil.which("ISCC") or next((str(path) for path in (
        Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Inno Setup 7" / "ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ) if path.exists()), None)
    if not iscc:
        print("未安装 Inno Setup；EXE 已生成，安装包需要 ISCC.exe。")
        return
    subprocess.run([iscc, "installer.iss"], cwd=ROOT, check=True)
    print(f"安装包：{ROOT / 'dist' / 'installer' / 'SocialInfo-Setup.exe'}")


if __name__ == "__main__":
    main()
