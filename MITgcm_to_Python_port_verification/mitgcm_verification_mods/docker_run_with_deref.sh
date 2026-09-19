#!/bin/bash
#
# Wrapper for docker_run_interactive that automatically dereferences symlinks
# in mounted code directories
#
# Usage: Just use this script instead of docker_run_interactive
#        It will automatically detect and dereference any symlinks
#
# Options:
#   -code <path>    Mount custom code directory (symlinks auto-dereferenced)
#   -taf_dir <path> Mount TAF directory (passed through unchanged)
#

# Get the original docker command arguments
DOCKER_ARGS=("$@")

# Find any -v mount arguments that mount code directories
# and replace them with temp directories that have dereferenced symlinks
NEW_ARGS=()
TEMP_DIRS=()

for ((i=0; i<${#DOCKER_ARGS[@]}; i++)); do
    arg="${DOCKER_ARGS[$i]}"

    # Special handling for -code argument (dereference symlinks)
    if [[ "$arg" == "-code" ]]; then
        # Next argument is the code directory path
        NEW_ARGS+=("$arg")
        i=$((i+1))
        CODE_PATH="${DOCKER_ARGS[$i]}"

        # Check if source has symlinks
        if [ -d "$CODE_PATH" ] && find "$CODE_PATH" -type l | grep -q .; then
            echo "Detected symlinks in code directory: $CODE_PATH"

            # Create temp directory
            TEMP_DIR="/tmp/docker_code_$(basename $CODE_PATH)_$$"
            mkdir -p "$TEMP_DIR"

            # Copy with dereferencing (-L flag)
            echo "  Dereferencing to: $TEMP_DIR"
            cp -rL "$CODE_PATH"/* "$TEMP_DIR/" 2>/dev/null || cp -rL "$CODE_PATH"/. "$TEMP_DIR/"

            # Track for cleanup
            TEMP_DIRS+=("$TEMP_DIR")

            # Use temp directory instead
            NEW_ARGS+=("$TEMP_DIR")
            echo "  ✓ Will use: $TEMP_DIR (dereferenced)"
        else
            # No symlinks, use as-is
            NEW_ARGS+=("$CODE_PATH")
        fi
    # Pass through -taf_dir unchanged (no dereferencing needed)
    elif [[ "$arg" == "-taf_dir" ]]; then
        NEW_ARGS+=("$arg")
        i=$((i+1))
        NEW_ARGS+=("${DOCKER_ARGS[$i]}")
        echo "TAF directory: ${DOCKER_ARGS[$i]} (passed through)"
    else
        NEW_ARGS+=("$arg")
    fi
done

# Run docker with modified arguments
echo ""
echo "Running docker with dereferenced symlinks..."
docker_run_interactive "${NEW_ARGS[@]}"

# Cleanup temp directories
if [ ${#TEMP_DIRS[@]} -gt 0 ]; then
    echo ""
    echo "Cleaning up temporary directories..."
    for dir in "${TEMP_DIRS[@]}"; do
        rm -rf "$dir"
        echo "  Removed: $dir"
    done
fi
