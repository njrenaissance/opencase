"""Extract all ZIP files from a source directory into a single destination.

Each ZIP is first extracted into a subfolder named after the ZIP file,
then all subfolders are merged into the destination directory. Files
that already exist at the destination path are skipped.

Usage:
    python scripts/extract_zips.py /path/to/zips /path/to/output
"""

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


def extract_zips(src_dir: Path, dest_dir: Path) -> None:
    zips = sorted(src_dir.glob("*.zip"))
    if not zips:
        print(f"No ZIP files found in {src_dir}")
        return

    print(f"Found {len(zips)} ZIP file(s)")
    dest_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        for zf_path in zips:
            folder_name = zf_path.stem
            extract_to = tmp_path / folder_name
            print(f"Extracting {zf_path.name} -> {folder_name}/")

            with zipfile.ZipFile(zf_path, "r") as zf:
                zf.extractall(extract_to)

        # Merge all extracted folders into dest, skipping collisions
        skipped = 0
        copied = 0
        for folder in sorted(tmp_path.iterdir()):
            if not folder.is_dir():
                continue
            for file in folder.rglob("*"):
                if not file.is_file():
                    continue
                rel = file.relative_to(tmp_path)
                target = dest_dir / rel
                if target.exists():
                    print(f"  SKIP (exists): {rel}")
                    skipped += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
                copied += 1

    print(f"\nDone. Copied {copied} file(s), skipped {skipped} collision(s).")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <zip_directory> <output_directory>")
        sys.exit(1)

    extract_zips(Path(sys.argv[1]), Path(sys.argv[2]))
