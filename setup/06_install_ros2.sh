#!/usr/bin/env bash
# 06_install_ros2.sh
# Install ROS2 Jazzy Jalisco on Ubuntu 24.04 (Noble) inside WSL2.
# Run once with sudo. Takes ~5 minutes depending on internet speed.
#
# After installation, source ROS2 in every new terminal:
#   source /opt/ros/jazzy/setup.bash
# Or add to ~/.bashrc (see bottom of this script for instructions).
#
# Reference: https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html

set -euo pipefail

echo "=== ROS2 Jazzy Install (Ubuntu 24.04) ==="

# [1/5] Locale
echo "[1/5] Configuring locale..."
locale-gen en_US en_US.UTF-8
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# [2/5] Universe repo + curl
echo "[2/5] Enabling universe repository..."
apt-get install -y -qq software-properties-common curl
add-apt-repository -y universe

# [3/5] ROS2 apt repo
echo "[3/5] Adding ROS2 apt repository..."
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
    http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
    | tee /etc/apt/sources.list.d/ros2.list > /dev/null
apt-get update -qq

# [4/5] Install ROS2 base + tools
echo "[4/5] Installing ROS2 Jazzy base + tools..."
# ros-jazzy-ros-base: core ROS2 without GUI tools (suitable for WSL2 headless)
apt-get install -y \
    ros-jazzy-ros-base \
    python3-colcon-common-extensions \
    python3-rosdep \
    ros-jazzy-teleop-twist-keyboard

# [5/5] rosdep init (ignore if already done)
echo "[5/5] Initialising rosdep..."
rosdep init 2>/dev/null || true
sudo -u "${SUDO_USER:-$USER}" rosdep update

echo ""
echo "=== ROS2 Jazzy installed ==="
echo ""
echo "To use ROS2, source it in every new terminal:"
echo "  source /opt/ros/jazzy/setup.bash"
echo ""
echo "To add it permanently to your shell:"
echo "  echo 'source /opt/ros/jazzy/setup.bash' >> ~/.bashrc"
echo ""
echo "Quick test:"
echo "  source /opt/ros/jazzy/setup.bash && ros2 topic list"
echo ""
echo "Run the Hunter SE bridge node:"
echo "  source /opt/ros/jazzy/setup.bash"
echo "  python3 src/hunter_se_node.py"
