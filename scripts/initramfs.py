#!/usr/bin/env python3
import os
import shutil

import utilities.boot_img as boot_img
import utilities.cpio as cpio
from extract import BOOT_IMG

# Output directory
CACHE_DIR = os.path.join("..", "work", "initramfs")
os.makedirs(CACHE_DIR, exist_ok=True)

# Where we put the compressed kernel
VMZ_FILE = os.path.join(CACHE_DIR, "vmlinuz")

# Extracted initramfs rootfs directory
EXTRACTED_DIR = os.path.join(CACHE_DIR, "extracted")
os.makedirs(EXTRACTED_DIR, exist_ok=True)

PATCHES_DIR = "patches"

# Files to copy into the extracted initramfs before repacking.
# Each entry is (src relative to PATCHES_DIR, dest relative to EXTRACTED_DIR).
PATCHES = [
    ("98-custom", "init.d/98-custom"),
]

def extract_kernel():
    if not os.path.exists(BOOT_IMG):
        raise FileNotFoundError(f"{BOOT_IMG} not found")

    with open(BOOT_IMG, "rb") as f:
        # Read boot header
        header = boot_img.read_boot_header(f)
        print("Header:", header)

        # Read file headers
        file_headers = boot_img.read_file_headers(f, header['files_off'], header['files_cnt'])
        print(f"Found {len(file_headers)} files in boot.img")

        # Look for kernel file
        kernel_header = None
        for fh in file_headers:
            if fh['name'] == 'kernel':
                kernel_header = fh
                break

        if kernel_header is None:
            raise ValueError("kernel file not found in boot.img")

        # Extract kernel
        f.seek(kernel_header['offset'])
        data = f.read(kernel_header['size'])

        with open(VMZ_FILE, 'wb') as out_f:
            out_f.write(data)
        print(f"Extracted kernel -> {VMZ_FILE} ({kernel_header['size']} bytes)")

def extract_initramfs(vmlinuz_file=VMZ_FILE):
    if not os.path.exists(vmlinuz_file):
        raise FileNotFoundError(f"{vmlinuz_file} not found")

    print(f"Reading {vmlinuz_file}...")

    with open(vmlinuz_file, "rb") as f:
        data = f.read()

    # Naive search for CPIO magic bytes (070701 for new ASCII format)
    # Extra 00 to make sure this is actually a CPIO archive and not just the header inside the kernel lol
    cpio_magic = b"07070100"
    cpio_start = data.find(cpio_magic)
    print(hex(cpio_start))
    if cpio_start == -1:
        raise ValueError("No cpio initramfs found in vmlinuz")

    print(f"CPIO initramfs found at offset {cpio_start}")

    # Write the raw cpio archive to a temporary file
    temp_cpio = os.path.join(CACHE_DIR, "initramfs.cpio")
    with open(temp_cpio, "wb") as f:
        f.write(data[cpio_start:])

    # Extract cpio (device files that require root are silently skipped)
    print("Extracting initramfs...")
    cpio.extract(temp_cpio, EXTRACTED_DIR)
    print(f"Initramfs extracted to {EXTRACTED_DIR}")

    # Apply patches
    for src_rel, dest_rel in PATCHES:
        src = os.path.join(PATCHES_DIR, src_rel)
        dest = os.path.join(EXTRACTED_DIR, dest_rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)
        print(f"Patched {dest_rel}")

    # Repack the initramfs as a cpio archive with root ownership
    repacked_cpio = os.path.join(CACHE_DIR, "initramfs-repacked.cpio")
    cpio.pack(EXTRACTED_DIR, repacked_cpio, uid=0, gid=0)
    print(f"Repacked initramfs as {repacked_cpio}")

def main():
    extract_kernel()
    extract_initramfs()

if __name__ == "__main__":
    main()
