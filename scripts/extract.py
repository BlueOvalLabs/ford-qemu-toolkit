#!/usr/bin/env python3
import os
from utilities import vbf
from download import CACHE_DIR as DOWNLOAD_CACHE_DIR

CACHE_DIR = os.path.join("cache", "extracted")
os.makedirs(CACHE_DIR, exist_ok=True)

EXTRACT = {
    "PU5T-14H486-GAM.vbf": [
        "ecg2-wrlinux-image-product-release-ford-ecg2-s32g2xx.squashfs-lzo.verity",
        "boot.img"
    ],
}

BOOT_IMG = os.path.join(CACHE_DIR, "boot.img")

def extract_vbf_file(vbf_file_path: str, files_to_extract):
    """Extract only specified files from a VBF file."""
    if not os.path.exists(vbf_file_path):
        raise FileNotFoundError(f"{vbf_file_path} does not exist")

    print(f"Reading {vbf_file_path}...")
    with open(vbf_file_path, "rb") as f:
        data = f.read()

    parsed = vbf.parse_vbf(data)
    vbf_files = parsed.get("files", {})

    for file_name in files_to_extract:
        if file_name not in vbf_files:
            raise ValueError(f"{file_name} not found in {vbf_file_path}")

        out_path = os.path.join(CACHE_DIR, file_name)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        print(f"Extracting {file_name} -> {out_path}")
        with open(out_path, "wb") as out_f:
            out_f.write(vbf_files[file_name]["data"])


def main():
    for vbf_name, files_list in EXTRACT.items():
        vbf_path = os.path.join(DOWNLOAD_CACHE_DIR, vbf_name)
        extract_vbf_file(vbf_path, files_list)

if __name__ == "__main__":
    main()
