# TAF Docker Support - Implementation Summary

**Date**: 2026-08-20  
**Status**: ✅ Complete

---

## Overview

Added support for mounting a TAF (Tangent linear and Adjoint Model Compiler) directory in the MITgcm docker container. This allows users to run adjoint/tangent linear builds inside the containerized environment.

---

## Changes Made

### 1. docker_run_interactive.sh

**File**: `/Users/ifenty/git_repo_others/MITgcm_verification_docker/scripts/docker_run_interactive.sh`

**Changes**:
- Added `-taf_dir <path>` argument parsing
- Validates TAF directory exists and is absolute path
- Warns if `staf` executable not found in directory
- Mounts TAF directory to `/taf` in container
- Mounts `~/.ssh` directory (read-only) to `/home/mitgcm/.ssh` for license keys
- Updates PATH environment variable to include `/taf`
- Updated help text and usage examples

**Key Code Sections**:

```bash
# Argument parsing
-taf_dir)
    TAF_DIR="$2"
    if [[ ! "$TAF_DIR" = /* ]]; then
        echo "Error: -taf_dir path must be absolute"
        exit 1
    fi
    ...

# Docker mount arguments
if [[ -n "$TAF_DIR" ]]; then
    MOUNT_ARGS="$MOUNT_ARGS -v $TAF_DIR:/taf"
    if [[ -d "$HOME/.ssh" ]]; then
        MOUNT_ARGS="$MOUNT_ARGS -v $HOME/.ssh:/home/mitgcm/.ssh:ro"
    fi
fi

# Environment arguments
if [[ -n "$TAF_DIR" ]]; then
    ENV_ARGS="$ENV_ARGS -e PATH=/taf:/usr/local/sbin:..."
fi
```

### 2. docker_run_with_deref.sh

**File**: `/Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments/mitgcm_verification_mods/docker_run_with_deref.sh`

**Changes**:
- Updated to recognize and pass through `-taf_dir` argument
- TAF directory is NOT dereferenced (unlike code directories)
- Added usage documentation for TAF support

**Key Code Section**:

```bash
# Pass through -taf_dir unchanged (no dereferencing needed)
elif [[ "$arg" == "-taf_dir" ]]; then
    NEW_ARGS+=("$arg")
    i=$((i+1))
    NEW_ARGS+=("${DOCKER_ARGS[$i]}")
    echo "TAF directory: ${DOCKER_ARGS[$i]} (passed through)"
```

### 3. Documentation Files

**Created**:
- `TAF_DOCKER_USAGE.md` - User-facing documentation with examples
- `TAF_IMPLEMENTATION_SUMMARY.md` - This file, technical implementation details
- `test_taf_mount.sh` - Test script to verify TAF mounting works

---

## Usage Examples

### Basic Usage

```bash
# Run with TAF only
docker_run_interactive.sh -taf_dir /Users/ifenty/TAF

# Run with custom code and TAF
docker_run_interactive.sh \
  -code /path/to/custom/code \
  -taf_dir /Users/ifenty/TAF

# Using symlink dereferencer wrapper
./docker_run_with_deref.sh \
  -code /path/to/kpp_mods \
  -taf_dir /Users/ifenty/TAF
```

### Inside Container

```bash
# Verify staf is available
which staf
# Output: /taf/staf

# Build with TAF
cd lab_sea/build
../../../tools/genmake2 -mods=/custom_code -optfile=$OPTFILE
make depend
make adall
```

---

## Technical Details

### Mount Points

| Host Path | Container Path | Mode | Purpose |
|-----------|----------------|------|---------|
| `$TAF_DIR` | `/taf` | rw | TAF installation |
| `~/.ssh` | `/home/mitgcm/.ssh` | ro | License keys |

### Environment Variables

- **PATH**: Updated to include `/taf` as first component
- **Full PATH**: `/taf:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/mitgcm/tools`

### Security Considerations

1. **SSH Directory**: Mounted read-only to prevent container from modifying host SSH config
2. **TAF Directory**: Mounted read-write since TAF may need to write temporary files
3. **No Copy**: Files are mounted (linked), not copied, for performance and to avoid duplication

---

## Design Decisions

### Why Mount Instead of Copy?

- **Performance**: TAF directories can be large; mounting is instantaneous
- **Updates**: Changes to TAF installation on host are immediately available in container
- **Disk Space**: No duplication of TAF installation

### Why Not Dereference TAF Directory?

Unlike the `-code` directory (which may contain symlinks to MITgcm source that need dereferencing), the TAF directory:
- Is typically a self-contained installation
- May have internal symlinks that should be preserved
- Does not have the same "symlink to repo" issue as code directories

### Why Mount ~/.ssh Read-Only?

- TAF needs to read SSH keys for license validation
- Container should NOT be able to modify host SSH configuration
- Read-only mount provides necessary access while maintaining security

---

## Testing

### Test Script

```bash
cd mitgcm_verification_mods
./test_taf_mount.sh /path/to/taf
```

This will:
1. Launch container with TAF mounted
2. Verify `staf` is in PATH
3. Check SSH directory is accessible
4. Display mount points and permissions

### Manual Testing

```bash
# Start container
./docker_run_with_deref.sh -taf_dir /Users/ifenty/TAF

# Inside container, verify
which staf              # Should output: /taf/staf
ls -la ~/.ssh          # Should show SSH keys
echo $PATH | grep taf  # Should show /taf in PATH
staf -version          # Should show TAF version (if license valid)
```

---

## Backwards Compatibility

✅ **Fully backwards compatible**

- Existing scripts work unchanged (TAF support is optional)
- `-code` argument continues to work as before
- No changes to Dockerfile required
- No changes to container image required

---

## Future Enhancements

Possible future improvements:

1. **TAF Version Check**: Warn if TAF version is very old
2. **License Validation**: Pre-check TAF license before mounting
3. **Multiple TAF Versions**: Support mounting multiple TAF versions simultaneously
4. **TAF Environment Variables**: Support additional TAF-specific env vars if needed

---

## Files Modified

| File | Location | Changes |
|------|----------|---------|
| `docker_run_interactive.sh` | `MITgcm_verification_docker/scripts/` | Added `-taf_dir` support |
| `docker_run_with_deref.sh` | `1D_Mixing_Experiments/mitgcm_verification_mods/` | Pass through TAF args |
| `TAF_DOCKER_USAGE.md` | `1D_Mixing_Experiments/mitgcm_verification_mods/` | User documentation |
| `test_taf_mount.sh` | `1D_Mixing_Experiments/mitgcm_verification_mods/` | Test script |
| `TAF_IMPLEMENTATION_SUMMARY.md` | `1D_Mixing_Experiments/mitgcm_verification_mods/` | This file |

---

## Summary

✅ **TAF directory mounting**: Mount specified directory to `/taf`  
✅ **SSH key access**: Mount `~/.ssh` read-only for license validation  
✅ **PATH configuration**: `/taf` added to PATH for `staf` access  
✅ **Wrapper support**: Works with symlink dereferencing wrapper  
✅ **Documentation**: Complete usage guide and implementation details  
✅ **Testing**: Test script provided for verification  
✅ **Backwards compatible**: Optional feature, existing usage unchanged

TAF support is now fully integrated into the MITgcm docker workflow.
