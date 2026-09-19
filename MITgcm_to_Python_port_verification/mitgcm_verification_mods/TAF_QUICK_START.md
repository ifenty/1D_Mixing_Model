# TAF Docker - Quick Start Guide

## Basic Command

```bash
docker_run_interactive.sh -taf_dir /path/to/taf
```

## Common Workflows

### 1. Interactive Shell with TAF

```bash
cd /path/to/MITgcm_verification_docker/scripts
./docker_run_interactive.sh -taf_dir ~/TAF
```

### 2. Custom Code + TAF

```bash
./docker_run_interactive.sh \
  -code /path/to/custom/code \
  -taf_dir ~/TAF
```

### 3. With Symlink Dereferencing

```bash
cd mitgcm_verification_mods
./docker_run_with_deref.sh \
  -code kpp_mods \
  -taf_dir ~/TAF
```

## Inside Container

```bash
# Verify TAF is available
which staf
# => /taf/staf

# Build with adjoint
cd lab_sea/build
../../../tools/genmake2 -mods=/custom_code -optfile=$OPTFILE
make depend
make adall

# Or tangent linear
make ftlall
```

## What Gets Mounted

| Host | Container | Access |
|------|-----------|--------|
| Your TAF dir | `/taf` | read-write |
| `~/.ssh` | `/home/mitgcm/.ssh` | read-only |

## Troubleshooting

```bash
# Check staf is in PATH
echo $PATH | grep /taf

# Check staf executable
ls -lh /taf/staf

# Check SSH keys mounted
ls -la ~/.ssh

# Test TAF
staf -version
```

## Requirements

- TAF installation with `staf` executable
- SSH key in `~/.ssh` for license
- Docker image `mitgcm:latest` built

## More Info

- Full docs: `TAF_DOCKER_USAGE.md`
- Test: `./test_taf_mount.sh /path/to/taf`
