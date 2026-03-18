PYTHON     := python3
SCRIPTS    := scripts
PLATFORM   := platform

NCPU := $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

# ── Renode ────────────────────────────────────────────────────────────────────
RENODE_SRC   := renode
RENODE_BUILD := $(RENODE_SRC)/output
RENODE_BIN   := $(RENODE_BUILD)/bin/Release/Renode

# Map uname -m → Renode's --host-arch flag.
# macOS ARM reports 'arm64'; Linux ARM reports 'aarch64'; x86-64 maps to 'i386'.
RENODE_HOST_ARCH := $(shell uname -m | grep -qE '^(arm64|aarch64)$$' && echo aarch64 || echo i386)

# ── Artefacts ─────────────────────────────────────────────────────────────────
WORK        := work
DOWNLOADS   := $(WORK)/downloads
EXTRACTED   := $(WORK)/extracted
INITRAMFS   := $(WORK)/initramfs
ROOTFS_IMG  := $(WORK)/rootfs.img
LOGS_BIN    := $(WORK)/logs.bin
DTB         := $(PLATFORM)/ford-ecg2.dtb
DTS         := $(PLATFORM)/ford-ecg2.dts

# ─────────────────────────────────────────────────────────────────────────────
.PHONY: all boot renode dtb download extract initramfs rootfs check-dtc \
        clean distclean

all: boot

# ── Renode build ──────────────────────────────────────────────────────────────
# build.sh handles nested submodule init automatically (detects uninitialised
# submodules via `git submodule status` and runs --init --recursive as needed).
$(RENODE_BIN): $(RENODE_SRC)/build.sh
	cd $(RENODE_SRC) && ./build.sh --host-arch $(RENODE_HOST_ARCH)

renode: $(RENODE_BIN)

# ── Dependency checks ─────────────────────────────────────────────────────────
check-dtc:
	@command -v dtc >/dev/null 2>&1 || { \
	    echo "ERROR: 'dtc' (device-tree-compiler) not found in PATH."; \
	    echo "  macOS:  brew install dtc"; \
	    echo "  Debian: apt install device-tree-compiler"; \
	    exit 1; }

# ── Device tree ───────────────────────────────────────────────────────────────
$(DTB): $(DTS) | check-dtc
	dtc -I dts -O dtb -o $@ $<

dtb: $(DTB)

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
boot: $(RENODE_BIN) $(DTB) $(INITRAMFS) $(ROOTFS_IMG) $(LOGS_BIN)
	cd $(SCRIPTS) && RENODE=$(CURDIR)/$(RENODE_BIN) ./boot.sh

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	rm -rf $(WORK)

distclean: clean
	rm -f $(DTB)
	rm -rf $(RENODE_BUILD)