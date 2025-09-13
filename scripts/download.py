#!/usr/bin/env python3
import os
import requests
from urllib.parse import urlparse

CACHE_DIR = os.path.join("cache", "downloads")
os.makedirs(CACHE_DIR, exist_ok=True)

# List of files to download
DOWNLOADS = [
    # 14H4181 contains bootloader_upgrade.bin, netloader-boot.img (we don't need these for now)
    # version 2.0.5.19
    #"https://vehiclesoftware.ford.com/e8ff06b7-e1a1-493f-ae68-9a1e9458dbd4_PU5T-14H481-GAD.vbf",

    # 14H486 contains boot.img, ecg2-wrlinux-image-product-release-ford-ecg2-s32g2xx.squashfs-lzo.verity
    # version 2.0.5.1522
    "https://vehiclesoftware.ford.com/f6daadd4-775d-476e-a981-1440844fa868_PU5T-14H486-GAM.vbf",
    #"https://ivsu.binaries.ford.com/swparts/PU5T-14H486-GAM_1721250604000.VBF"
    
    # version 1.0.28.25
    #"https://ivsu.binaries.ford.com/swparts/PU5T-14H486-AAD_1634062348000.VBF"
]

def sanitize_filename(url):
    base = os.path.basename(urlparse(url).path)
    base, ext = os.path.splitext(base)

    if "_" in base and base.count("_") == 1:
        prefix, rest = base.split("_")
        # If this is UUID-prefixed, strip the prefix
        if len(prefix) == 36:
            return rest + ext.lower()
        return prefix + ext.lower()

    return base + ext.lower()

def download_file(url, dest_dir):
    filename = sanitize_filename(url)
    dest_path = os.path.join(dest_dir, filename)
    
    print(f"Downloading {url} -> {dest_path}")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    
    print(f"Downloaded {filename}")

def main():
    for url in DOWNLOADS:
        download_file(url, CACHE_DIR)

if __name__ == "__main__":
    main()
