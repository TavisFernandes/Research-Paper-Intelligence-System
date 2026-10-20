"""
Reassemble bge_m3_finetuned.pth from split chunks.

After cloning the repo, run this script once from the repo root:
    python Model_Training/BGE_M3_Model/reassemble_model.py
"""

import os
import pathlib

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "bge_m3_finetuned.pth"
CHUNK_PATTERN = "bge_m3_finetuned.part"


def reassemble():
    # Collect parts in sorted order
    parts = sorted(SCRIPT_DIR.glob(f"{CHUNK_PATTERN}*"))
    if not parts:
        print("No .part files found. Make sure you cloned the full repo including LFS files.")
        return

    print(f"Found {len(parts)} part(s): {[p.name for p in parts]}")

    if OUTPUT_FILE.exists():
        print(f"{OUTPUT_FILE.name} already exists — skipping reassembly.")
        return

    print(f"Reassembling into {OUTPUT_FILE} ...")
    total_bytes = 0
    with open(OUTPUT_FILE, "wb") as out:
        for part in parts:
            print(f"  Appending {part.name} ({part.stat().st_size / 1e6:.1f} MB) ...")
            with open(part, "rb") as f:
                while chunk := f.read(4 * 1024 * 1024):
                    out.write(chunk)
                    total_bytes += len(chunk)

    print(f"Done! {OUTPUT_FILE.name} written ({total_bytes / 1e9:.2f} GB)")


if __name__ == "__main__":
    reassemble()
