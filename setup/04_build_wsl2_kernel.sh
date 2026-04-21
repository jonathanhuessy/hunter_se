#!/usr/bin/env bash
# 04_build_wsl2_kernel.sh
# Builds a custom WSL2 kernel with gs_usb (candleLight CAN adapter) support.
# Run inside WSL2 Ubuntu with sudo. Takes ~15 minutes on first build.
#
# After running:
#   1. In Windows PowerShell: wsl --shutdown
#   2. Reopen WSL2 terminal
#   3. sudo bash setup/02_setup_can_interface.sh

set -euo pipefail

BUILD_DIR="$HOME/wsl2-kernel"

echo "=== WSL2 Custom Kernel Build (gs_usb / candleLight CAN adapter) ==="
echo ""

# 1. Install build dependencies
echo "[1/6] Installing build dependencies..."
apt-get update -qq
apt-get install -y -qq build-essential flex bison libssl-dev libelf-dev bc dwarves pahole git

# 2. Detect running kernel version and matching source tag
RUNNING_KERNEL=$(uname -r)
echo "[2/6] Running kernel: $RUNNING_KERNEL"
WSL_VERSION=$(echo "$RUNNING_KERNEL" | grep -oP "[\d.]+(?=-microsoft)")
TAG="linux-msft-wsl-${WSL_VERSION}"
echo "      Using source tag: $TAG"

# 3. Clone kernel source (shallow clone of matching tag)
echo "[3/6] Cloning WSL2 kernel source..."
if [ -d "$BUILD_DIR/.git" ]; then
    echo "      Already cloned, reusing $BUILD_DIR"
    cd "$BUILD_DIR"
    git fetch --tags --quiet
    git checkout "$TAG" --quiet
else
    git clone --depth=1 --branch "$TAG" \
        https://github.com/microsoft/WSL2-Linux-Kernel.git \
        "$BUILD_DIR"
    cd "$BUILD_DIR"
fi

# 4. Configure: enable CAN + gs_usb on top of Microsofts default WSL config
echo "[4/6] Configuring kernel..."
cp Microsoft/config-wsl .config
scripts/config --enable CONFIG_CAN
scripts/config --enable CONFIG_CAN_RAW
scripts/config --enable CONFIG_CAN_DEV
scripts/config --enable CONFIG_CAN_GS_USB
# Disable IKHEADERS: causes kheaders_data.tar.xz build failure in WSL2 environments
scripts/config --disable CONFIG_IKHEADERS
# olddefconfig accepts all new symbols at their default values (no stdin needed)
# avoids broken-pipe exit from "yes | make oldconfig" under set -euo pipefail
make olddefconfig > /dev/null 2>&1
echo "      gs_usb config:"
grep "CONFIG_CAN_GS_USB" .config

# 5. Build
NPROC=$(nproc)
echo "[5/6] Building with $NPROC cores (this takes ~15 minutes)..."
make -j"$NPROC" KCONFIG_CONFIG=.config

OUTPUT="$BUILD_DIR/arch/x86/boot/bzImage"
echo "      Done: $OUTPUT ($(du -sh $OUTPUT | cut -f1))"

# 6. Install kernel and update .wslconfig
echo "[6/6] Installing kernel..."
WIN_USER=$(cmd.exe /c echo %USERNAME% 2>/dev/null | tr -d "\r")
WIN_KERNEL_DIR="/mnt/c/Users/${WIN_USER}/wsl2-kernel"
mkdir -p "$WIN_KERNEL_DIR"
cp "$OUTPUT" "$WIN_KERNEL_DIR/bzImage"
echo "      Copied to: $WIN_KERNEL_DIR/bzImage"

WSLCFG="/mnt/c/Users/${WIN_USER}/.wslconfig"
WIN_PATH="C:\\\\Users\\\\${WIN_USER}\\\\wsl2-kernel\\\\bzImage"

if grep -q "\[wsl2\]" "$WSLCFG" 2>/dev/null; then
    if grep -q "^kernel=" "$WSLCFG"; then
        sed -i "s|^kernel=.*|kernel=${WIN_PATH}|" "$WSLCFG"
    else
        sed -i "/\[wsl2\]/a kernel=${WIN_PATH}" "$WSLCFG"
    fi
else
    printf "\n[wsl2]\nkernel=%s\n" "$WIN_PATH" >> "$WSLCFG"
fi
echo "      .wslconfig updated: $WSLCFG"

echo ""
echo "=== Build complete! ==="
echo ""
echo "Next steps:"
echo "  1. In Windows PowerShell:  wsl --shutdown"
echo "  2. Reopen WSL2 terminal"
echo "  3. Verify:  sudo modprobe gs_usb && echo OK"
echo "  4. Run:     sudo bash setup/02_setup_can_interface.sh"