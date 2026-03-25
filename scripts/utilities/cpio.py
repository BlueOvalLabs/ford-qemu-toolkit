#!/usr/bin/env python3
"""CPIO utility (newc / 070701 format)."""

import os
import socket as _socket
import stat
from pathlib import Path
from typing import Union

CPIO_MAGIC = b"070701"
TRAILER_NAME = "TRAILER!!!"
HEADER_LEN = 110  # fixed size of a newc header


def _pad4(data: bytes) -> bytes:
    rem = len(data) % 4
    if rem:
        data += b"\x00" * (4 - rem)
    return data


def _make_header(
    ino: int,
    mode: int,
    uid: int,
    gid: int,
    nlink: int,
    mtime: int,
    filesize: int,
    devmajor: int,
    devminor: int,
    rdevmajor: int,
    rdevminor: int,
    namesize: int,
) -> bytes:
    return (
        "070701"
        f"{ino:08X}{mode:08X}{uid:08X}{gid:08X}{nlink:08X}{mtime:08X}"
        f"{filesize:08X}{devmajor:08X}{devminor:08X}{rdevmajor:08X}{rdevminor:08X}"
        f"{namesize:08X}00000000"
    ).encode("ascii")


def pack(src_dir: Union[str, Path], dest_file: Union[str, Path], uid: int = 0, gid: int = 0) -> None:
    """Create a CPIO newc archive from *src_dir*, overriding all uid/gid to the given values."""
    src_dir = Path(src_dir)
    ino = 1

    with open(dest_file, "wb") as f:

        def _write_entry(name: str, mode: int, filesize: int, mtime: int,
                         nlink: int, rdevmajor: int, rdevminor: int, payload: bytes) -> None:
            nonlocal ino
            name_bytes = name.encode() + b"\x00"
            header = _make_header(
                ino=ino, mode=mode, uid=uid, gid=gid,
                nlink=nlink, mtime=mtime, filesize=filesize,
                devmajor=0, devminor=0,
                rdevmajor=rdevmajor, rdevminor=rdevminor,
                namesize=len(name_bytes),
            )
            ino += 1
            f.write(_pad4(header + name_bytes))
            if payload:
                f.write(_pad4(payload))

        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames.sort()

            rel = Path(dirpath).relative_to(src_dir)
            name = str(rel) if str(rel) != "." else "."
            st = os.lstat(dirpath)
            _write_entry(
                name=name,
                mode=(st.st_mode & 0o7777) | stat.S_IFDIR,
                filesize=0, mtime=int(st.st_mtime), nlink=2,
                rdevmajor=0, rdevminor=0, payload=b"",
            )

            for filename in sorted(filenames):
                filepath = Path(dirpath) / filename
                name = str(filepath.relative_to(src_dir))
                st = os.lstat(filepath)

                if stat.S_ISLNK(st.st_mode):
                    payload = os.readlink(filepath).encode()
                    _write_entry(
                        name=name, mode=st.st_mode,
                        filesize=len(payload), mtime=int(st.st_mtime), nlink=1,
                        rdevmajor=0, rdevminor=0, payload=payload,
                    )
                elif stat.S_ISREG(st.st_mode):
                    with open(filepath, "rb") as fdata:
                        payload = fdata.read()
                    _write_entry(
                        name=name, mode=st.st_mode,
                        filesize=len(payload), mtime=int(st.st_mtime), nlink=1,
                        rdevmajor=0, rdevminor=0, payload=payload,
                    )
                elif stat.S_ISBLK(st.st_mode) or stat.S_ISCHR(st.st_mode):
                    _write_entry(
                        name=name, mode=st.st_mode,
                        filesize=0, mtime=int(st.st_mtime), nlink=1,
                        rdevmajor=os.major(st.st_rdev),
                        rdevminor=os.minor(st.st_rdev),
                        payload=b"",
                    )
                elif stat.S_ISFIFO(st.st_mode) or stat.S_ISSOCK(st.st_mode):
                    _write_entry(
                        name=name, mode=st.st_mode,
                        filesize=0, mtime=int(st.st_mtime), nlink=1,
                        rdevmajor=0, rdevminor=0, payload=b"",
                    )

        # Trailer
        trailer = TRAILER_NAME.encode() + b"\x00"
        header = _make_header(
            ino=0, mode=0, uid=0, gid=0, nlink=1, mtime=0, filesize=0,
            devmajor=0, devminor=0, rdevmajor=0, rdevminor=0,
            namesize=len(trailer),
        )
        f.write(_pad4(header + trailer))


def _create_entry(dest: Path, name: str, mode: int, mtime: int,
                  payload: bytes, rdevmajor: int, rdevminor: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    file_type = stat.S_IFMT(mode)

    if file_type == stat.S_IFDIR:
        dest.mkdir(parents=True, exist_ok=True)
        os.utime(dest, (mtime, mtime))
    elif file_type == stat.S_IFLNK:
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        os.symlink(payload.decode("utf-8", errors="replace"), dest)
    elif file_type == stat.S_IFREG:
        dest.write_bytes(payload)
        os.chmod(dest, stat.S_IMODE(mode))
        os.utime(dest, (mtime, mtime))
    elif file_type in (stat.S_IFBLK, stat.S_IFCHR):
        try:
            os.mknod(dest, mode, os.makedev(rdevmajor, rdevminor))
        except PermissionError:
            print(f"  skipping device {name} (requires root)")
    elif file_type == stat.S_IFIFO:
        os.mkfifo(dest, stat.S_IMODE(mode))
    elif file_type == stat.S_IFSOCK:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        try:
            s.bind(str(dest))
        finally:
            s.close()
    else:
        raise NotImplementedError(f"Unsupported file type in CPIO archive: {oct(file_type)} for entry {name}")


def extract(src_file: Union[str, Path], dest_dir: Union[str, Path]) -> None:
    """Extract a CPIO newc archive to *dest_dir*."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with open(src_file, "rb") as f:
        data = f.read()

    offset = 0
    while offset + HEADER_LEN <= len(data):
        if data[offset:offset + 6] != CPIO_MAGIC:
            break

        hdr = data[offset:offset + HEADER_LEN].decode("ascii")
        mode      = int(hdr[14:22], 16)
        mtime     = int(hdr[46:54], 16)
        filesize  = int(hdr[54:62], 16)
        rdevmajor = int(hdr[78:86], 16)
        rdevminor = int(hdr[86:94], 16)
        namesize  = int(hdr[94:102], 16)
        offset += HEADER_LEN

        name_raw = data[offset:offset + namesize]
        name = name_raw.rstrip(b"\x00").decode("utf-8", errors="replace")
        offset += namesize
        offset += (4 - (HEADER_LEN + namesize) % 4) % 4  # pad to 4-byte boundary

        if name == TRAILER_NAME:
            break

        payload = data[offset:offset + filesize]
        offset += filesize
        offset += (4 - filesize % 4) % 4

        _create_entry(dest_dir / name, name, mode, mtime, payload, rdevmajor, rdevminor)

