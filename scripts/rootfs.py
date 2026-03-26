#!/usr/bin/env python3
import math
import os

from gpt_image.disk import Disk
from gpt_image.partition import Partition, PartitionType

from extract import CACHE_DIR as EXTRACT_CACHE_DIR
from utilities.ext4 import make_empty_ext4

CACHE_DIR = os.path.join("..", "work")

SQUASHFS_NAME = "ecg2-wrlinux-image-product-release-ford-ecg2-s32g2xx.squashfs-lzo.verity"
SQUASHFS_PATH = os.path.join(EXTRACT_CACHE_DIR, SQUASHFS_NAME)
ROOTFS_IMG = os.path.join(CACHE_DIR, "rootfs.img")

MiB = 1024 * 1024


def align_up(x, alignment):
    return int(math.ceil(x / alignment) * alignment)



def mk_bootfs() -> bytes:
    """Build a 512-byte RAW0 bootfs header block."""
    MAGIC = b"RAW0"
    blk = bytearray(512)
    blk[0:4] = MAGIC
    blk[4:8] = (1).to_bytes(4, "little")
    antimagic = (-int.from_bytes(MAGIC, "little") - 1) & 0xFFFFFFFF
    named_block_start = 1
    blk[8:12] = named_block_start.to_bytes(4, "little")
    blk[12:16] = (antimagic - named_block_start).to_bytes(4, "little")
    return bytes(blk)


def main():

    if not os.path.exists(SQUASHFS_PATH):
        raise FileNotFoundError(f"{SQUASHFS_PATH} not found - run extract.py first")

    print(f"Reading squashfs from {SQUASHFS_PATH}...")
    with open(SQUASHFS_PATH, "rb") as f:
        squashfs_data = f.read()

    squashfs_size = len(squashfs_data)
    partition_size = align_up(squashfs_size, MiB)

    PERM_SIZE = 8 * MiB
    DPS_SIZE = 8 * MiB
    DATA_SIZE = 128 * MiB
    BOOTFS_SIZE = 2 * MiB
    GPT_OVERHEAD = 2 * MiB

    TOTAL_SIZE = partition_size + PERM_SIZE + DPS_SIZE + DATA_SIZE + BOOTFS_SIZE + GPT_OVERHEAD

    disk_size = align_up(TOTAL_SIZE, MiB)

    print(f"Creating {ROOTFS_IMG} ({disk_size // MiB} MiB)...")
    if os.path.exists(ROOTFS_IMG):
        os.remove(ROOTFS_IMG)
    disk = Disk(ROOTFS_IMG)
    disk.create(disk_size)

    system_a = Partition("system_a", size=partition_size, type_guid=PartitionType.LINUX_FILE_SYSTEM.value)
    perm     = Partition("perm",     size=PERM_SIZE,        type_guid=PartitionType.LINUX_FILE_SYSTEM.value)
    dps      = Partition("dps",      size=DPS_SIZE,        type_guid=PartitionType.LINUX_FILE_SYSTEM.value)
    data     = Partition("data",     size=DATA_SIZE,        type_guid=PartitionType.LINUX_FILE_SYSTEM.value)
    boot_fs  = Partition("boot_fs",  size=BOOTFS_SIZE,        type_guid=PartitionType.LINUX_FILE_SYSTEM.value)

    disk.table.partitions.add(system_a)
    disk.table.partitions.add(perm)
    disk.table.partitions.add(dps)
    disk.table.partitions.add(data)
    disk.table.partitions.add(boot_fs)
    disk.commit()

    print("Writing squashfs to system_a...")
    system_a.write_data(disk, squashfs_data)

    print("Writing ext4 partitions (perm, dps, data)...")
    perm.write_data(disk, make_empty_ext4(PERM_SIZE))
    dps.write_data(disk, make_empty_ext4(DPS_SIZE))
    data.write_data(disk, make_empty_ext4(DATA_SIZE))

    print("Writing boot_fs (RAW0)...")
    boot_fs.write_data(disk, mk_bootfs())

    disk.commit()
    print(f"Done: {ROOTFS_IMG}")
    print(disk)


if __name__ == "__main__":
    main()
