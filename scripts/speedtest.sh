#!/bin/bash
# Internet Speed Test Script using CloudFlare
# Usage: bash speedtest.sh

set -e

echo "======================================="
echo "    Internet Speed Test"
echo "======================================="
echo ""

# Download test
echo "[1/2] Testing Download speed..."
DOWNLOAD_SPEED=$(curl -o /dev/null -w "%{speed_download}" --max-time 30 https://speed.cloudflare.com/__down?bytes=50000000 2>/dev/null)
DOWNLOAD_MBPS=$(echo "$DOWNLOAD_SPEED" | awk '{printf "%.2f", ($1*8/1000000)}')
DOWNLOAD_MBS=$(echo "$DOWNLOAD_SPEED" | awk '{printf "%.2f", ($1/1000000)}')
echo "   Download: $DOWNLOAD_MBPS Mbps ($DOWNLOAD_MBS MB/s)"
echo ""

# Upload test
echo "[2/2] Testing Upload speed..."
UPLOAD_SPEED=$(dd if=/dev/zero bs=1M count=10 2>/dev/null | curl -o /dev/null -w "%{speed_upload}" -X POST --data-binary @- --max-time 30 https://speed.cloudflare.com/__up 2>/dev/null)
UPLOAD_MBPS=$(echo "$UPLOAD_SPEED" | awk '{printf "%.2f", ($1*8/1000000)}')
UPLOAD_MBS=$(echo "$UPLOAD_SPEED" | awk '{printf "%.2f", ($1/1000000)}')
echo "   Upload:   $UPLOAD_MBPS Mbps ($UPLOAD_MBS MB/s)"
echo ""

echo "======================================="
echo "   Test completed!"
echo "======================================="
