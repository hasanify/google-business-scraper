"""Release preparation script for semantic-release.

Injected during semantic-release prepare lifecycle step:
1. Updates src/version.py with the release version.
2. Generates Windows PE version_info.txt.
3. Builds standalone GoogleBusinessScraper.exe using PyInstaller.
4. Removes temporary version_info.txt.
5. Verifies executable artifact in dist/.
"""

import os
import subprocess
import sys


def parse_version_tuple(ver_str: str) -> tuple:
    """Parse version string into 4-integer tuple for Windows FixedFileInfo."""
    cleaned = "".join(c for c in ver_str if c.isdigit() or c == ".")
    parts = [int(p) for p in cleaned.split(".") if p.isdigit()]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def generate_version_info(ver_str: str) -> str:
    """Generate PyInstaller Windows version info definition."""
    parts = parse_version_tuple(ver_str)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={parts},
    prodvers={parts},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Google Business Scraper'),
          StringStruct('FileDescription', 'Google Places POI Business Scraper GUI'),
          StringStruct('FileVersion', '{ver_str}'),
          StringStruct('InternalName', 'GoogleBusinessScraper-v{ver_str}'),
          StringStruct('LegalCopyright', 'Copyright (c) 2026'),
          StringStruct('OriginalFilename', 'GoogleBusinessScraper-v{ver_str}.exe'),
          StringStruct('ProductName', 'Google Business Scraper'),
          StringStruct('ProductVersion', '{ver_str}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    if len(sys.argv) < 2:
        print("[!] Error: Release version argument missing.", file=sys.stderr)
        sys.exit(1)

    version = sys.argv[1].lstrip("v")
    print(f"[*] Preparing release build for version: {version}")

    # 1. Update src/version.py
    version_file = os.path.join("src", "version.py")
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(f'"""Single source of truth for the application version."""\n\n__version__ = "{version}"\n')
    print(f"[*] Injected version {version} into {version_file}")

    # 2. Write temporary version_info.txt
    info_path = "version_info.txt"
    with open(info_path, "w", encoding="utf-8") as f:
        f.write(generate_version_info(version))

    try:
        # 3. Build standalone executable using active Python interpreter
        exe_basename = f"GoogleBusinessScraper-v{version}"
        build_cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconsole",
            "--onefile",
            "--version-file",
            info_path,
            "--name",
            exe_basename,
            "gui.py",
        ]
        print(f"[*] Running: {' '.join(build_cmd)}")
        result = subprocess.run(build_cmd, check=True)
    finally:
        # 4. Clean up temporary version resource
        if os.path.exists(info_path):
            os.remove(info_path)

    # 5. Verify output artifact exists
    dist_exe = os.path.join("dist", f"{exe_basename}.exe")
    if not os.path.exists(dist_exe):
        print(f"[!] Error: Executable was not created at {dist_exe}", file=sys.stderr)
        sys.exit(1)

    exe_size_mb = os.path.getsize(dist_exe) / (1024 * 1024)
    print(f"[+] Build successful: {dist_exe} ({exe_size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
