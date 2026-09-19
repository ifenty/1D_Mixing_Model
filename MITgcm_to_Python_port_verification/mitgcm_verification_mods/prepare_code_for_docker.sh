#!/bin/bash
#
# Prepare verification code directory for Docker by dereferencing softlinks
#
# Usage: ./prepare_code_for_docker.sh <experiment_name>
# Example: ./prepare_code_for_docker.sh 1D_ocean_ice_column
#

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <experiment_name>"
    echo "Example: $0 1D_ocean_ice_column"
    echo "         $0 lab_sea"
    exit 1
fi

EXPERIMENT=$1
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/${EXPERIMENT}/code_validation" && pwd)"
TEMP_DIR="/tmp/mitgcm_code_${EXPERIMENT}"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory does not exist: $SOURCE_DIR"
    exit 1
fi

echo "Preparing code for Docker..."
echo "  Source: $SOURCE_DIR"
echo "  Temp:   $TEMP_DIR"

# Remove old temp directory if it exists
if [ -d "$TEMP_DIR" ]; then
    echo "  Removing old temp directory..."
    rm -rf "$TEMP_DIR"
fi

# Create temp directory
mkdir -p "$TEMP_DIR"

# Copy files, dereferencing symlinks (-L flag)
echo "  Copying files (dereferencing symlinks)..."
cp -L "$SOURCE_DIR"/* "$TEMP_DIR/"

# Verify kpp_calc.F was copied correctly
if [ -f "$TEMP_DIR/kpp_calc.F" ]; then
    PARAM_COUNT=$(grep -c "PARAM_" "$TEMP_DIR/kpp_calc.F" || true)
    echo "  ✓ kpp_calc.F copied (${PARAM_COUNT} PARAM_ lines)"

    # Check for firstCall
    if grep -q "firstCall" "$TEMP_DIR/kpp_calc.F"; then
        echo "  ✓ firstCall logic present"
    else
        echo "  ⚠ Warning: firstCall logic not found"
    fi
else
    echo "  ⚠ Warning: kpp_calc.F not found in temp directory"
fi

echo ""
echo "✓ Done! Code prepared at: $TEMP_DIR"
echo ""
echo "Use this in your docker command:"
echo "  Instead of: ${SOURCE_DIR}"
echo "  Use:        ${TEMP_DIR}"
echo ""
