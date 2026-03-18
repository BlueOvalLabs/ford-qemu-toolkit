PYTHON     := python3
SCRIPTS    := scripts

# ── QEMU ──────────────────────────────────────────────────────────────────────
QEMU_SRC   := qemu
QEMU_BUILD := qemu/build
QEMU_BIN   := $(QEMU_BUILD)/qemu-system-aarch64-unsigned

NCPU := $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

# ── Artefacts ─────────────────────────────────────────────────────────────────
WORK        := work
DOWNLOADS   := $(WORK)/downloads
EXTRACTED   := $(WORK)/extracted
INITRAMFS   := $(WORK)/initramfs
ROOTFS_IMG  := $(WORK)/rootfs.img
LOGS_BIN    := $(WORK)/logs.bin

# ─────────────────────────────────────────────────────────────────────────────
.PHONY: all boot qemu download extract initramfs rootfs clean distclean

all: boot

# ── QEMU build ────────────────────────────────────────────────────────────────
$(QEMU_BUILD)/Makefile: $(QEMU_SRC)/configure
	mkdir -p $(QEMU_BUILD)
	cd $(QEMU_BUILD) && $(CURDIR)/$(QEMU_SRC)/configure \
	    --target-list=aarch64-softmmu

$(QEMU_BIN): $(QEMU_BUILD)/Makefile
	$(MAKE) -C $(QEMU_BUILD) -j$(NCPU)

qemu: $(QEMU_BIN)

# ── Python pipeline ───────────────────────────────────────────────────────────
UTILS := $(SCRIPTS)/utilities/vbf.py \
         $(SCRIPTS)/utilities/boot_img.py \
         $(SCRIPTS)/utilities/ext4.py

$(WORK):
	mkdir -p $@

$(DOWNLOADS): $(SCRIPTS)/download.py | $(WORK)
	cd $(SCRIPTS) && $(PYTHON) download.py

$(EXTRACTED): $(DOWNLOADS) $(SCRIPTS)/extract.py $(UTILS)
	cd $(SCRIPTS) && $(PYTHON) extract.py

$(INITRAMFS): $(EXTRACTED) $(SCRIPTS)/initramfs.py $(UTILS)
	cd $(SCRIPTS) && $(PYTHON) initramfs.py

$(ROOTFS_IMG): $(EXTRACTED) $(SCRIPTS)/rootfs.py $(UTILS)
	cd $(SCRIPTS) && $(PYTHON) rootfs.py

$(LOGS_BIN): | $(WORK)
	dd if=/dev/zero of=$@ bs=1M count=5

download:  $(DOWNLOADS)
extract:   $(EXTRACTED)
initramfs: $(INITRAMFS)
rootfs:    $(ROOTFS_IMG)

# ── Boot ──────────────────────────────────────────────────────────────────────
boot: $(QEMU_BIN) $(INITRAMFS) $(ROOTFS_IMG) $(LOGS_BIN)
	cd $(SCRIPTS) && QEMU=$(CURDIR)/$(QEMU_BIN) ./boot.sh

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	rm -rf $(WORK)

distclean: clean
	rm -rf $(QEMU_BUILD)
