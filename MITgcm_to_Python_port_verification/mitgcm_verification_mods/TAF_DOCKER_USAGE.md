# TAF Support in MITgcm Docker

## Overview

The MITgcm docker scripts now support mounting a TAF (Tangent linear and Adjoint Model Compiler) directory for use inside the container.

## Requirements

- TAF installation directory with `staf` executable
- SSH key in `~/.ssh` for TAF license validation

## Usage

### Basic TAF Mount

```bash
docker_run_interactive.sh -taf_dir /path/to/taf
```

### With Custom Code

```bash
docker_run_interactive.sh -code /path/to/custom/code -taf_dir /path/to/taf
```

### Using the Symlink Dereferencing Wrapper

```bash
./docker_run_with_deref.sh -code /path/to/custom/code -taf_dir /path/to/taf
```

## What Happens

When you specify `-taf_dir`:

1. **TAF Directory Mount**: The specified directory is mounted at `/taf` inside the container
2. **SSH Key Mount**: Your `~/.ssh` directory is mounted (read-only) at `/home/mitgcm/.ssh` for TAF license access
3. **PATH Update**: `/taf` is added to the PATH environment variable, making `staf` available

## Inside the Container

Once inside the container with TAF mounted:

```bash
# Check TAF is available
which staf
# Output: /taf/staf

# Use TAF with genmake2
cd 1D_ocean_ice_column/build
../../../tools/genmake2 -mods=/custom_code -optfile=$OPTFILE
make depend
make adall  # or other TAF-based targets
```

## Example: KPP Modifications with TAF

```bash
# From the project directory
cd mitgcm_verification_mods

# Run with dereferenced symlinks and TAF
./docker_run_with_deref.sh \
  -code /Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments/mitgcm_verification_mods/kpp_mods \
  -taf_dir /Users/ifenty/TAF

# Inside container
cd lab_sea/build
../../../tools/genmake2 -mods=/custom_code -optfile=$OPTFILE
make depend
make adall
```

## Security Note

The `~/.ssh` directory is mounted **read-only** for security. This allows TAF to access license keys without giving the container write access to your SSH configuration.

## Troubleshooting

### "staf: command not found"

The TAF directory wasn't mounted correctly. Check:
- Path is absolute
- `staf` executable exists in the specified directory
- You used the `-taf_dir` flag

### TAF License Errors

Check:
- `~/.ssh` directory exists and contains necessary keys
- Keys have correct permissions (typically 600 for private keys)
- TAF license is valid and accessible

### PATH Issues

If `staf` isn't in PATH after mounting, the PATH environment wasn't set correctly. This should be automatic when using `-taf_dir`, but you can manually check:

```bash
echo $PATH | grep /taf
```

## Implementation Details

### Modified Files

- `/Users/ifenty/git_repo_others/MITgcm_verification_docker/scripts/docker_run_interactive.sh`
  - Added `-taf_dir` argument parsing
  - Mounts TAF directory and ~/.ssh
  - Updates PATH environment variable

- `/Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments/mitgcm_verification_mods/docker_run_with_deref.sh`
  - Passes through `-taf_dir` unchanged (no dereferencing needed)
  - Continues to dereference symlinks in `-code` directories

### Docker Run Command

When `-taf_dir` is specified, the docker run command includes:

```bash
docker run --rm -it \
    -v /path/to/taf:/taf \
    -v ~/.ssh:/home/mitgcm/.ssh:ro \
    -e PATH=/taf:/usr/local/sbin:/usr/local/bin:... \
    ...
```
