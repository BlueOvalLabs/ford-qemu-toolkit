#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# QEMU can be overridden by the caller (e.g. from the Makefile).
# Default to the binary built from the local qemu submodule.
QEMU="${QEMU:-${SCRIPT_DIR}/../qemu/build/qemu-system-aarch64-unsigned}"
CACHE="${SCRIPT_DIR}/../work"

MASK_SERVICES=(
  # Stub this with /tmp/netinit.done created in 98-custom
  # TODO: Does a bunch of stuff to setup custom network interface we should replicate
  nw_util.service

  # Stability Monitor, shuts down system after a few minutes
  # Mask this to keep the system alive for debugging the root cause
  sm-sysmgr.service

  # FNV2 services, require CAN/hardware?
  fnv2vim.service
  fnv2ipcd.service
  fnv2_ipc_vim_renice.service

  # ??? Misc services
  tcpdump.service # Network Packet Capture
  #cpmd.service # Cloud Package Manager Daemon        
  pimd.service # PIMD multicast routing service

  # ALM package manager, launcher will crash
  #almbridge.service
  #launcher.service
  #pacmand.service

  # Will fail when selinux=0
  selinuxsetenforce.service

  # Seems to burn CPU for no reason?
  #powerman.service
)

MASK_ARGS=""
for svc in "${MASK_SERVICES[@]}"; do
    MASK_ARGS="${MASK_ARGS} systemd.mask=${svc}"
done

"${QEMU}" \
  -M virt \
  -cpu cortex-a53 \
  -m 4096M \
  -nographic \
  -kernel "${CACHE}/initramfs/vmlinuz" \
  -initrd "${CACHE}/initramfs/initramfs-repacked.cpio" \
  -append "rootwait console=ttyAMA0 iomem=relaxed boot_bank=a selinux=0 ${MASK_ARGS}" \
  -device virtio-blk-device,drive=drive0 \
  -drive "file=${CACHE}/rootfs.img,if=none,format=raw,id=drive0" \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -device virtio-net-device,netdev=net0 

# proper host networking is possible on macOS, but require sudo:
  #-netdev vmnet-host,id=net0 \
