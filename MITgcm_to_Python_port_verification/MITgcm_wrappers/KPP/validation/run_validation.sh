#!/bin/bash
#
# run_validation.sh - Complete validation workflow for KPP wrapper vs Python port
#
# This script:
# 1. Runs Python KPP port on a scenario and exports inputs/outputs
# 2. Converts exported data to wrapper binary format
# 3. Runs MITgcm wrapper on all timesteps
# 4. Compares outputs and reports results
#
# Usage:
#   ./run_validation.sh <scenario_yaml> <output_dir> <num_steps>
#
# Example:
#   ./run_validation.sh ../../1D_Mixing_Model/configuration_yamls/test_scenario.yaml \
#                       ./validation_output 10
#

set -e  # Exit on error

if [ $# -lt 2 ]; then
    echo "Usage: $0 <scenario_yaml> <output_dir> [num_steps]"
    echo ""
    echo "Example:"
    echo "  $0 ../../1D_Mixing_Model/configuration_yamls/initial_conditions.yaml \\"
    echo "     ./validation_output 10"
    exit 1
fi

SCENARIO="$1"
OUTPUT_DIR="$2"
NUM_STEPS="${3:-10}"  # Default 10 timesteps

VALIDATION_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_ENV="/Users/ifenty/miniforge3/envs/ecco/bin/python"

# Check prerequisites
if [ ! -f "$SCENARIO" ]; then
    echo "Error: Scenario file not found: $SCENARIO"
    exit 1
fi

if [ ! -f "${VALIDATION_DIR}/export_kpp_port_data.py" ]; then
    echo "Error: Validation scripts not found in: $VALIDATION_DIR"
    exit 1
fi

echo "=============================================="
echo "KPP Wrapper Validation Workflow"
echo "=============================================="
echo "Scenario:     $SCENARIO"
echo "Output:       $OUTPUT_DIR"
echo "Timesteps:    $NUM_STEPS"
echo ""

# Step 1: Export Python port data
echo "Step 1: Running Python KPP port and exporting data..."
echo "----------------------------------------------"
$PYTHON_ENV "${VALIDATION_DIR}/export_kpp_port_data.py" \
    --scenario "$SCENARIO" \
    --output_dir "$OUTPUT_DIR" \
    --num_steps "$NUM_STEPS"

if [ $? -ne 0 ]; then
    echo "Error: Export failed!"
    exit 1
fi
echo ""

# Step 2: Convert to wrapper format
echo "Step 2: Converting to wrapper binary format..."
echo "----------------------------------------------"
$PYTHON_ENV "${VALIDATION_DIR}/convert_to_wrapper_format.py" \
    --input_dir "$OUTPUT_DIR"

if [ $? -ne 0 ]; then
    echo "Error: Conversion failed!"
    exit 1
fi
echo ""

# Step 3: Run wrapper on all timesteps
echo "Step 3: Running MITgcm wrapper on all timesteps..."
echo "----------------------------------------------"
"${VALIDATION_DIR}/run_wrapper_batch.sh" "$OUTPUT_DIR"

if [ $? -ne 0 ]; then
    echo "Error: Wrapper batch run failed!"
    exit 1
fi
echo ""

# Step 4: Compare outputs
echo "Step 4: Comparing wrapper vs port outputs..."
echo "----------------------------------------------"
$PYTHON_ENV "${VALIDATION_DIR}/compare_wrapper_vs_port.py" \
    --validation_dir "$OUTPUT_DIR" \
    --rtol 1e-12 \
    --verbose

RESULT=$?
echo ""

# Summary
echo "=============================================="
if [ $RESULT -eq 0 ]; then
    echo "✓ VALIDATION PASSED"
    echo "  Wrapper outputs match Python port"
    echo "  (within relative tolerance 1e-12)"
else
    echo "✗ VALIDATION FAILED"
    echo "  Differences found between wrapper and port"
    echo "  See details above"
fi
echo "=============================================="
echo ""
echo "Results saved to: $OUTPUT_DIR"
echo ""

exit $RESULT
