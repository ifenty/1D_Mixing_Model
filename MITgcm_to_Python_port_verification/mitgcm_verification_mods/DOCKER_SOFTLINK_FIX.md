# Docker Softlink Fix for Code Directories

## Problem
Docker's `-v` mount preserves softlinks, which breaks if the softlink target is outside the mounted directory.

## Solution: Use tar pipe with automatic dereferencing

Instead of mounting the directory directly, pipe it through tar with `-h` (dereference) flag.

## Method 1: Pre-populate a volume

```bash
# One-time setup per experiment
EXPERIMENT="1D_ocean_ice_column"
CODE_DIR="$PWD/${EXPERIMENT}/code_validation"

# Create a Docker volume
docker volume create mitgcm_code_${EXPERIMENT}

# Copy code into volume, dereferencing symlinks
docker run --rm \
    -v "${CODE_DIR}:/source:ro" \
    -v mitgcm_code_${EXPERIMENT}:/dest \
    alpine sh -c "cp -rL /source/* /dest/"

# Now use the volume in your docker_run_interactive
# Instead of: -v ${CODE_DIR}:/code
# Use:        -v mitgcm_code_${EXPERIMENT}:/code
```

## Method 2: Inline tar with dereference (cleanest for one-off runs)

Add this to your docker_run_interactive command:

```bash
# Create temp container with dereferenced code
CODE_DIR="$PWD/1D_ocean_ice_column/code_validation"

# Option A: Create temp directory on host
TEMP_CODE="/tmp/docker_code_$$"
(cd "$CODE_DIR" && tar ch --exclude=.git .) | tar xC "$TEMP_CODE"

# Then mount TEMP_CODE instead of CODE_DIR
docker run ... -v "$TEMP_CODE:/code" ...

# Cleanup after: rm -rf "$TEMP_CODE"
```

## Method 3: Simplest - Create alias/function in ~/.bashrc

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Automatically dereference symlinks when mounting directories to docker
docker_mount_deref() {
    local SRC="$1"
    local DEST="$2"

    if [ -d "$SRC" ] && find "$SRC" -maxdepth 1 -type l | grep -q .; then
        # Has symlinks - create temp with dereferenced files
        local TEMP_DIR="/tmp/docker_mount_$$_$(basename $SRC)"
        mkdir -p "$TEMP_DIR"
        (cd "$SRC" && tar ch .) | tar xC "$TEMP_DIR"
        echo "$TEMP_DIR:$DEST"
        # Note: You'll need to manually cleanup $TEMP_DIR after docker exits
    else
        echo "$SRC:$DEST"
    fi
}

# Usage in docker command:
# docker run -v $(docker_mount_deref ./code_validation /code) ...
```

## Method 4: RECOMMENDED - Make real copies for validation runs

Since validation runs are specific and reproducible, just keep real file copies:

```bash
# One-time: Convert softlinks to real files in code_validation directories
cd mitgcm_verification_mods

for exp in 1D_ocean_ice_column lab_sea; do
    cd "${exp}/code_validation"

    # For each symlink, replace with real file
    find . -type l | while read link; do
        target=$(readlink "$link")
        rm "$link"
        cp "$target" "$link"
    done

    cd ../..
done
```

This way your `code_validation` directories have real files and Docker will work normally.

## RECOMMENDED APPROACH

For validation work, I recommend **Method 4** - just keep real file copies in the validation directories since:

1. ✅ No Docker complications
2. ✅ No extra scripts needed  
3. ✅ Validation configs should be frozen snapshots anyway
4. ✅ You can still edit the master `kpp_mods/kpp_calc.F` and copy when ready

When you update `kpp_mods/kpp_calc.F`, just run:
```bash
cp kpp_mods/kpp_calc.F 1D_ocean_ice_column/code_validation/
cp kpp_mods/kpp_calc.F lab_sea/code_validation/
```

Or create a simple sync script if you prefer.
