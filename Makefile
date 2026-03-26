PYTHON     := python3
SCRIPTS    := scripts
VENV       := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_STAMP := $(VENV)/.installed

# ── QEMU ──────────────────────────────────────────────────────────────────────
QEMU_SRC   := qemu
QEMU_BUILD := qemu/build
UNAME      := $(shell uname)
ifeq ($(UNAME),Darwin)
QEMU_BIN   := $(QEMU_BUILD)/qemu-system-aarch64-unsigned
else
QEMU_BIN   := $(QEMU_BUILD)/qemu-system-aarch64
endif

NCPU := $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

# ── Artefacts ─────────────────────────────────────────────────────────────────
WORK        := work
DOWNLOADS   := $(WORK)/downloads
EXTRACTED   := $(WORK)/extracted
INITRAMFS   := $(WORK)/initramfs
ROOTFS_IMG  := $(WORK)/rootfs.img

# ─────────────────────────────────────────────────────────────────────────────
.PHONY: all boot qemu download extract initramfs rootfs clean distclean venv

all: boot

# ── Venv ──────────────────────────────────────────────────────────────────────
$(VENV_STAMP): requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q -r requirements.txt
	touch $@

venv: $(VENV_STAMP)

# ── QEMU build ────────────────────────────────────────────────────────────────
$(QEMU_BUILD)/Makefile: $(QEMU_SRC)/configure
	mkdir -p $(QEMU_BUILD)
	cd $(QEMU_BUILD) && $(CURDIR)/$(QEMU_SRC)/configure \
	    --target-list=aarch64-softmmu \
	    --enable-slirp

$(QEMU_BIN): $(QEMU_BUILD)/Makefile
	$(MAKE) -C $(QEMU_BUILD) -j$(NCPU)

qemu: $(QEMU_BIN)

# ── Python pipeline ───────────────────────────────────────────────────────────
UTILS := $(SCRIPTS)/utilities/vbf.py \
         $(SCRIPTS)/utilities/boot_img.py \
         $(SCRIPTS)/utilities/ext4.py

$(WORK):
	mkdir -p $@

$(DOWNLOADS): $(SCRIPTS)/download.py | $(VENV_STAMP) $(WORK)
	cd $(SCRIPTS) && $(CURDIR)/$(VENV_PYTHON) download.py

$(EXTRACTED): $(DOWNLOADS) $(SCRIPTS)/extract.py $(UTILS) | $(VENV_STAMP)
	cd $(SCRIPTS) && $(CURDIR)/$(VENV_PYTHON) extract.py

$(INITRAMFS): $(EXTRACTED) $(SCRIPTS)/initramfs.py $(UTILS) | $(VENV_STAMP)
	cd $(SCRIPTS) && $(CURDIR)/$(VENV_PYTHON) initramfs.py

$(ROOTFS_IMG): $(EXTRACTED) $(SCRIPTS)/rootfs.py $(UTILS) | $(VENV_STAMP)
	cd $(SCRIPTS) && $(CURDIR)/$(VENV_PYTHON) rootfs.py

download:  $(DOWNLOADS)
extract:   $(EXTRACTED)
initramfs: $(INITRAMFS)
rootfs:    $(ROOTFS_IMG)

# ── Boot ──────────────────────────────────────────────────────────────────────
boot: $(QEMU_BIN) $(INITRAMFS) $(ROOTFS_IMG)
	cd $(SCRIPTS) && QEMU=$(CURDIR)/$(QEMU_BIN) ./boot.sh

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	rm -rf $(WORK)

distclean: clean
	rm -rf $(QEMU_BUILD) $(VENV)
