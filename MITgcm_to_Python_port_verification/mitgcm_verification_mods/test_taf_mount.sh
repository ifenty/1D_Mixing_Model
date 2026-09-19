#!/bin/bash
#
# Test script to verify TAF mounting works correctly
#
# Usage: ./test_taf_mount.sh /path/to/taf
#

if [ $# -eq 0 ]; then
    echo "Usage: $0 /path/to/taf"
    echo ""
    echo "Example:"
    echo "  $0 /Users/ifenty/TAF"
    exit 1
fi

TAF_DIR="$1"

if [ ! -d "$TAF_DIR" ]; then
    echo "Error: TAF directory does not exist: $TAF_DIR"
    exit 1
fi

if [ ! -f "$TAF_DIR/staf" ]; then
    echo "Error: staf executable not found in $TAF_DIR"
    exit 1
fi

echo "========================================"
echo "Testing TAF Docker Mount"
echo "========================================"
echo ""
echo "TAF Directory: $TAF_DIR"
echo "SSH Directory: $HOME/.ssh"
echo ""

# Create a test command that will verify TAF is available
TEST_CMD='echo "=== Testing TAF availability ===" && \
          echo "PATH: $PATH" && \
          echo "" && \
          echo "Checking for staf:" && \
          which staf && \
          echo "" && \
          echo "staf location:" && \
          ls -lh $(which staf) && \
          echo "" && \
          echo "SSH keys available:" && \
          ls -la ~/.ssh/ 2>/dev/null | head -10 && \
          echo "" && \
          echo "=== TAF mount test successful ==="'

# Run docker with TAF mounted
echo "Launching docker container with TAF..."
echo ""

docker run --rm -it \
    --platform linux/$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/') \
    -v "$TAF_DIR:/taf" \
    -v "$HOME/.ssh:/home/mitgcm/.ssh:ro" \
    -e PATH="/taf:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    -w /home/mitgcm \
    mitgcm:latest \
    /bin/bash -c "$TEST_CMD"

echo ""
echo "========================================"
echo "Test complete"
echo "========================================"
