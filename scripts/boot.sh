#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
CACHE="${PROJECT_ROOT}/work"

# RENODE can be overridden by the caller (e.g. from the Makefile).
# Default to the binary built from the local renode submodule.
RENODE="${RENODE:-${PROJECT_ROOT}/renode/output/bin/Release/Renode}"

if [ ! -f "${CACHE}/logs.bin" ]; then
    echo "Creating logs.bin..."
    dd if=/dev/zero of="${CACHE}/logs.bin" bs=1M count=5 2>/dev/null
fi

# Run Renode from the project root so that @-paths in boot.resc resolve
# correctly (e.g. @work/rootfs.img, @platform/ford-ecg2.repl).
cd "${PROJECT_ROOT}"

exec "${RENODE}" --console scripts/boot.resc