#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# QEMU can be overridden by the caller (e.g. from the Makefile).
# Default to the binary built from the local qemu submodule.
QEMU="${QEMU:-${SCRIPT_DIR}/../qemu/build/qemu-system-aarch64-unsigned}"
CACHE="${SCRIPT_DIR}/../work"

if [ ! -f "${CACHE}/logs.bin" ]; then
    echo "Creating logs.bin..."
    dd if=/dev/zero of="${CACHE}/logs.bin" bs=1M count=5 2>/dev/null
fi

"${QEMU}" \
  -M virt \
  -cpu cortex-a53 \
  -m 4096M \
  -nographic \
  -kernel "${CACHE}/initramfs/vmlinuz" \
  -initrd "${CACHE}/initramfs/initramfs-repacked.cpio" \
  -append 'rootwait console=ttyAMA0 iomem=relaxed boot_bank=a' \
  -device virtio-blk-device,drive=drive0 \
  -drive "file=${CACHE}/rootfs.img,if=none,format=raw,id=drive0" \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -device virtio-net-device,netdev=net0 \
  -device virtio-blk-device,drive=drive1 \
  -drive "file=${CACHE}/logs.bin,if=none,format=raw,id=drive1"

# proper host networking is possible on macOS, but require sudo:
  #-netdev vmnet-host,id=net0 \
