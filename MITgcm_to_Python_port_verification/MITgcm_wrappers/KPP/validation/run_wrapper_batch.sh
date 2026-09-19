#!/bin/bash
#
# run_wrapper_batch.sh - Run MITgcm KPP wrapper on all exported timesteps
#
# Usage:
#   ./run_wrapper_batch.sh <validation_data_dir>
#
# For each timestep_XXXX directory:
#   - Copies input.bin to wrapper's input location
#   - Runs wrapper
#   - Saves CSV output to timestep_XXXX/wrapper_output.csv
#

set -e  # Exit on error

if [ $# -ne 1 ]; then
    echo "Usage: $0 <validation_data_dir>"
    exit 1
fi

VALIDATION_DIR="$1"
WRAPPER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WRAPPER_EXE="${WRAPPER_DIR}/kpp_wrapper"

if [ ! -f "$WRAPPER_EXE" ]; then
    echo "Error: Wrapper executable not found: $WRAPPER_EXE"
    echo "Build it first: cd ${WRAPPER_DIR} && make"
    exit 1
fi

if [ ! -f "${VALIDATION_DIR}/manifest.yaml" ]; then
    echo "Error: ${VALIDATION_DIR}/manifest.yaml not found"
    echo "Run export_kpp_port_data.py and convert_to_wrapper_format.py first"
    exit 1
fi

echo "Running KPP wrapper on all timesteps in: ${VALIDATION_DIR}"
echo "Wrapper: ${WRAPPER_EXE}"
echo ""

# Count timesteps
TIMESTEP_DIRS=$(find "$VALIDATION_DIR" -maxdepth 1 -type d -name "timestep_*" | sort)
NUM_TIMESTEPS=$(echo "$TIMESTEP_DIRS" | wc -l | tr -d ' ')

echo "Found $NUM_TIMESTEPS timesteps to process"
echo ""

# Process each timestep
COUNT=0
for TIMESTEP_DIR in $TIMESTEP_DIRS; do
    COUNT=$((COUNT + 1))
    TIMESTEP_NAME=$(basename "$TIMESTEP_DIR")

    INPUT_BIN="${TIMESTEP_DIR}/input.bin"
    OUTPUT_CSV="${TIMESTEP_DIR}/wrapper_output.csv"

    if [ ! -f "$INPUT_BIN" ]; then
        echo "[$COUNT/$NUM_TIMESTEPS] ✗ $TIMESTEP_NAME: input.bin not found (skip)"
        continue
    fi

    echo -n "[$COUNT/$NUM_TIMESTEPS] Processing $TIMESTEP_NAME... "

    # Create symbolic link to input.bin (wrapper expects input.bin in current dir)
    cd "$WRAPPER_DIR"
    ln -sf "$INPUT_BIN" input.bin

    # Run wrapper, save output
    if "$WRAPPER_EXE" > "$OUTPUT_CSV" 2>&1; then
        # Count output lines
        NUM_LINES=$(grep -c "OUTPUT_MIXING" "$OUTPUT_CSV" || echo "0")
        echo "✓ ($NUM_LINES output lines)"
    else
        echo "✗ Wrapper failed (see $OUTPUT_CSV for errors)"
    fi
done

echo ""
echo "✓ Batch run complete!"
echo ""
echo "Next step: Compare outputs"
echo "  python $(dirname "$0")/compare_wrapper_vs_port.py --validation_dir $VALIDATION_DIR"
