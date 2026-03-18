"""
Minimal ext4 filesystem builder.

Creates a single-block-group ext4 image with a root directory and a JBD2
journal, so it can be mounted with data=journal.

Block layout
────────────
  0          : boot sector (1024 B zeros) + superblock (1024 B)
  1          : block group descriptor table
  2          : block bitmap
  3          : inode bitmap
  4 – 35     : inode table  (512 inodes × 256 B = 32 blocks)
  36         : root directory data
  37 – 292   : journal  (JOURNAL_BLOCKS = 256 blocks, ~1 MiB)
  293 +      : free data blocks

Supports sizes up to ~128 MiB (single block group, 4 KB blocks).
"""

import struct
import uuid as _uuid

BLOCK_SIZE       = 4096
INODE_SIZE       = 256
INODES_PER_GROUP = 512
BLOCKS_PER_GROUP = 32768
JOURNAL_BLOCKS   = 256      # 1 MiB journal; block 0 of journal = JBD2 superblock

# Special inode numbers
ROOT_INO         = 2
JOURNAL_INO      = 8

# Inodes 1-10 are reserved; first user inode is 11
RESERVED_INODES  = 10

# ── ext4 feature flags ───────────────────────────────────────────────────────
COMPAT_HAS_JOURNAL        = 0x0004
COMPAT_DIR_INDEX          = 0x0020
INCOMPAT_FILETYPE         = 0x0002
INCOMPAT_EXTENTS          = 0x0040
RO_COMPAT_SPARSE_SUPER    = 0x0001
RO_COMPAT_LARGE_FILE      = 0x0002

EXT4_EXTENTS_FL           = 0x00080000
EXT4_EXTENT_MAGIC         = 0xF30A

# ── JBD2 constants ───────────────────────────────────────────────────────────
JBD2_MAGIC           = 0xC03B3998
JBD2_SUPERBLOCK_V2   = 4       # h_blocktype for journal superblock v2

# Directory entry file types
FT_DIR = 2


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pack_superblock(total_blocks: int, free_blocks: int, free_inodes: int,
                     fs_uuid: bytes) -> bytes:
    sb = bytearray(1024)

    def w32(off, v): struct.pack_into('<I', sb, off, v)
    def w16(off, v): struct.pack_into('<H', sb, off, v)

    w32(0,   INODES_PER_GROUP)                                          # s_inodes_count
    w32(4,   total_blocks)                                              # s_blocks_count_lo
    w32(8,   0)                                                         # s_r_blocks_count_lo
    w32(12,  free_blocks)                                               # s_free_blocks_count_lo
    w32(16,  free_inodes)                                               # s_free_inodes_count
    w32(20,  0)                                                         # s_first_data_block
    w32(24,  2)                                                         # s_log_block_size (4096)
    w32(28,  2)                                                         # s_log_cluster_size
    w32(32,  BLOCKS_PER_GROUP)                                          # s_blocks_per_group
    w32(36,  BLOCKS_PER_GROUP)                                          # s_clusters_per_group
    w32(40,  INODES_PER_GROUP)                                          # s_inodes_per_group
    w32(44,  0)                                                         # s_mtime
    w32(48,  0)                                                         # s_wtime
    w16(52,  0)                                                         # s_mnt_count
    w16(54,  0xFFFF)                                                    # s_max_mnt_count (-1)
    w16(56,  0xEF53)                                                    # s_magic
    w16(58,  1)                                                         # s_state (VALID_FS)
    w16(60,  1)                                                         # s_errors (CONTINUE)
    w16(62,  0)                                                         # s_minor_rev_level
    w32(64,  0)                                                         # s_lastcheck
    w32(68,  0)                                                         # s_checkinterval
    w32(72,  0)                                                         # s_creator_os (Linux)
    w32(76,  1)                                                         # s_rev_level (DYNAMIC)
    w16(80,  0)                                                         # s_def_resuid
    w16(82,  0)                                                         # s_def_resgid
    # EXT4_DYNAMIC_REV fields
    w32(84,  11)                                                        # s_first_ino
    w16(88,  INODE_SIZE)                                                # s_inode_size
    w16(90,  0)                                                         # s_block_group_nr
    w32(92,  COMPAT_HAS_JOURNAL | COMPAT_DIR_INDEX)                     # s_feature_compat
    w32(96,  INCOMPAT_FILETYPE | INCOMPAT_EXTENTS)                      # s_feature_incompat
    w32(100, RO_COMPAT_SPARSE_SUPER | RO_COMPAT_LARGE_FILE)             # s_feature_ro_compat
    sb[104:120] = fs_uuid                                               # s_uuid
    # s_volume_name[16], s_last_mounted[64]: zeros
    w32(224, JOURNAL_INO)                                               # s_journal_inum

    return bytes(sb)


def _pack_group_desc(block_bitmap: int, inode_bitmap: int, inode_table: int,
                     free_blocks: int, free_inodes: int) -> bytes:
    gd = bytearray(32)
    struct.pack_into('<I', gd,  0, block_bitmap)    # bg_block_bitmap_lo
    struct.pack_into('<I', gd,  4, inode_bitmap)    # bg_inode_bitmap_lo
    struct.pack_into('<I', gd,  8, inode_table)     # bg_inode_table_lo
    struct.pack_into('<H', gd, 12, free_blocks)     # bg_free_blocks_count_lo
    struct.pack_into('<H', gd, 14, free_inodes)     # bg_free_inodes_count_lo
    struct.pack_into('<H', gd, 16, 1)               # bg_used_dirs_count_lo
    return bytes(gd)


def _pack_inode(mode: int, size: int, links: int, blocks_512: int,
                flags: int, i_block: bytes) -> bytes:
    assert len(i_block) == 60
    inode = bytearray(INODE_SIZE)

    def w32(off, v): struct.pack_into('<I', inode, off, v)
    def w16(off, v): struct.pack_into('<H', inode, off, v)

    w16(0,   mode)
    w16(2,   0)                          # i_uid lo
    w32(4,   size & 0xFFFFFFFF)          # i_size_lo
    w32(8,   0)                          # i_atime
    w32(12,  0)                          # i_ctime
    w32(16,  0)                          # i_mtime
    w32(20,  0)                          # i_dtime
    w16(24,  0)                          # i_gid lo
    w16(26,  links)                      # i_links_count
    w32(28,  blocks_512)                 # i_blocks_lo (512-byte units)
    w32(32,  flags)                      # i_flags
    inode[40:100] = i_block              # extent tree / i_block[0..14]
    w16(128, 28)                         # i_extra_isize

    return bytes(inode)


def _extent_tree(logical: int, length: int, phys: int) -> bytes:
    """Inline extent tree: 12-byte header + 12-byte leaf + 36-byte pad = 60 bytes."""
    hdr = bytearray(12)
    struct.pack_into('<H', hdr, 0, EXT4_EXTENT_MAGIC)   # eh_magic
    struct.pack_into('<H', hdr, 2, 1)                    # eh_entries
    struct.pack_into('<H', hdr, 4, 4)                    # eh_max
    struct.pack_into('<H', hdr, 6, 0)                    # eh_depth (leaf)
    struct.pack_into('<I', hdr, 8, 0)                    # eh_generation

    leaf = bytearray(12)
    struct.pack_into('<I', leaf, 0, logical)             # ee_block
    struct.pack_into('<H', leaf, 4, length)              # ee_len (bit15=0 → initialised)
    struct.pack_into('<H', leaf, 6, 0)                   # ee_start_hi
    struct.pack_into('<I', leaf, 8, phys)                # ee_start_lo

    return bytes(hdr) + bytes(leaf) + b'\x00' * 36


def _pack_jbd2_superblock(journal_blocks: int, fs_uuid: bytes) -> bytes:
    """
    Build a JBD2 superblock v2 for a clean (empty) journal.
    All JBD2 fields are big-endian.
    s_start = 0 → kernel treats the journal as clean and skips replay.
    """
    blk = bytearray(BLOCK_SIZE)

    def w32be(off, v): struct.pack_into('>I', blk, off, v)

    # journal_header_t
    w32be(0,  JBD2_MAGIC)          # h_magic
    w32be(4,  JBD2_SUPERBLOCK_V2)  # h_blocktype
    w32be(8,  1)                   # h_sequence

    # journal_superblock_t (after header)
    w32be(12, BLOCK_SIZE)          # s_blocksize
    w32be(16, journal_blocks)      # s_maxlen
    w32be(20, 1)                   # s_first  (first usable block inside the journal)
    w32be(24, 1)                   # s_sequence
    w32be(28, 0)                   # s_start = 0 → clean journal, no replay needed
    # s_errno, s_feature_*: zeros
    blk[48:64] = fs_uuid           # s_uuid  (matches the ext4 superblock)
    w32be(64, 1)                   # s_nr_users

    return bytes(blk)


def _dir_entry(ino: int, rec_len: int, name: str, file_type: int) -> bytes:
    name_b = name.encode()
    entry = bytearray(rec_len)
    struct.pack_into('<I', entry, 0, ino)
    struct.pack_into('<H', entry, 4, rec_len)
    struct.pack_into('<B', entry, 6, len(name_b))
    struct.pack_into('<B', entry, 7, file_type)
    entry[8:8 + len(name_b)] = name_b
    return bytes(entry)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def make_empty_ext4(size_bytes: int) -> bytes:
    """
    Return a bytes object containing a minimal valid empty ext4 filesystem
    with a JBD2 journal.  Mountable with data=journal.

    Requirements:
      - size_bytes must be a multiple of BLOCK_SIZE (4096)
      - size_bytes must fit in one block group (≤ 128 MiB for 4 KB blocks)
    """
    if size_bytes % BLOCK_SIZE:
        raise ValueError(f"size_bytes must be a multiple of {BLOCK_SIZE}")
    total_blocks = size_bytes // BLOCK_SIZE
    if total_blocks > BLOCKS_PER_GROUP:
        raise ValueError(f"size exceeds single block group limit ({BLOCKS_PER_GROUP * BLOCK_SIZE} bytes)")

    inode_table_blocks = (INODES_PER_GROUP * INODE_SIZE) // BLOCK_SIZE   # 32 blocks

    # Fixed block addresses
    BLOCK_BITMAP_BLK = 2
    INODE_BITMAP_BLK = 3
    INODE_TABLE_BLK  = 4
    ROOT_DATA_BLK    = INODE_TABLE_BLK + inode_table_blocks              # 36
    JOURNAL_START    = ROOT_DATA_BLK + 1                                  # 37

    used_blocks = JOURNAL_START + JOURNAL_BLOCKS                          # 293
    free_blocks = total_blocks - used_blocks
    free_inodes = INODES_PER_GROUP - RESERVED_INODES                      # 502

    fs_uuid = _uuid.uuid4().bytes
    image   = bytearray(size_bytes)

    # ── Superblock ────────────────────────────────────────────────────────────
    image[1024:2048] = _pack_superblock(total_blocks, free_blocks, free_inodes, fs_uuid)

    # ── Block Group Descriptor Table (block 1) ────────────────────────────────
    gd = _pack_group_desc(BLOCK_BITMAP_BLK, INODE_BITMAP_BLK, INODE_TABLE_BLK,
                          free_blocks, free_inodes)
    image[BLOCK_SIZE:BLOCK_SIZE + 32] = gd

    # ── Block Bitmap (block 2): mark blocks 0..used_blocks-1 allocated ────────
    bb = bytearray(BLOCK_SIZE)
    for i in range(used_blocks // 8):
        bb[i] = 0xFF
    rem = used_blocks % 8
    if rem:
        bb[used_blocks // 8] = (1 << rem) - 1
    image[2 * BLOCK_SIZE:3 * BLOCK_SIZE] = bb

    # ── Inode Bitmap (block 3): mark reserved inodes 1-10 allocated ──────────
    # Inodes 1-8 → first byte = 0xFF; inodes 9-10 → bits 0-1 of second byte
    ib = bytearray(BLOCK_SIZE)
    ib[0] = 0xFF   # inodes 1-8
    ib[1] = 0x03   # inodes 9-10
    image[3 * BLOCK_SIZE:4 * BLOCK_SIZE] = ib

    inode_table_off = INODE_TABLE_BLK * BLOCK_SIZE

    # ── Root Directory Inode (inode 2 = index 1) ─────────────────────────────
    root_inode = _pack_inode(
        mode      = 0o040755,
        size      = BLOCK_SIZE,
        links     = 2,
        blocks_512= BLOCK_SIZE // 512,
        flags     = EXT4_EXTENTS_FL,
        i_block   = _extent_tree(0, 1, ROOT_DATA_BLK),
    )
    image[inode_table_off +     INODE_SIZE : inode_table_off + 2 * INODE_SIZE] = root_inode

    # ── Journal Inode (inode 8 = index 7) ────────────────────────────────────
    journal_size  = JOURNAL_BLOCKS * BLOCK_SIZE
    journal_inode = _pack_inode(
        mode      = 0o0100600,                               # regular file, rw-------
        size      = journal_size,
        links     = 1,
        blocks_512= JOURNAL_BLOCKS * (BLOCK_SIZE // 512),   # in 512-byte units
        flags     = EXT4_EXTENTS_FL,
        i_block   = _extent_tree(0, JOURNAL_BLOCKS, JOURNAL_START),
    )
    image[inode_table_off + 7 * INODE_SIZE : inode_table_off + 8 * INODE_SIZE] = journal_inode

    # ── Root Directory Data (block ROOT_DATA_BLK) ─────────────────────────────
    dot    = _dir_entry(ROOT_INO, 12,               '.', FT_DIR)
    dotdot = _dir_entry(ROOT_INO, BLOCK_SIZE - 12, '..', FT_DIR)
    dir_off = ROOT_DATA_BLK * BLOCK_SIZE
    image[dir_off:dir_off + 12]              = dot
    image[dir_off + 12:dir_off + BLOCK_SIZE] = dotdot

    # ── JBD2 Journal Superblock (first block of journal) ─────────────────────
    jbd2_off = JOURNAL_START * BLOCK_SIZE
    image[jbd2_off:jbd2_off + BLOCK_SIZE] = _pack_jbd2_superblock(JOURNAL_BLOCKS, fs_uuid)

    return bytes(image)