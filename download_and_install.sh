#!/bin/bash

# Download and Install Script for Binance Trading Bot
# Run this on a fresh Ubuntu 22.04 server

set -e

echo "=== Binance Trading Bot Download and Install ==="
echo "This script will download and install the trading bot on a fresh server"
echo

# Download the installation script
echo "Downloading installation script..."
curl -o fresh_install.sh https://raw.githubusercontent.com/misterchinkachuk/trade-bot/main/fresh_install.sh

# Make it executable
chmod +x fresh_install.sh

# Run the installation
echo "Starting installation..."
./fresh_install.sh

echo "Installation completed!"
