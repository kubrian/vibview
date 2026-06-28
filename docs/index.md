# vibview

Vibrational mode visualization tool for computational chemistry.

## Install

```bash
pip install git+https://github.com/kubrian/vibview.git
```

Requires Python 3.10+.

## Usage

```bash
# Launch the interactive viewer with the bundled H₂O example
vibview view

# Select a specific mode index
vibview view --mode 2

# Export an animation (GUI export, or convert then use export subcommand)
vibview convert water.hess orca -o water.h5
vibview export water.h5 native --format gif --name anim
vibview export water.h5 native --format mp4 --name anim
vibview export water.h5 native --format png --name frames/anim
vibview export water.h5 native --format mp4 --name anim --cycles 3

# Load your own data
vibview view water.hess orca
vibview view band.yaml phonopy

# Convert external formats to native HDF5 (faster loading, smaller files)
vibview convert water.hess orca -o water.h5
vibview convert band.yaml phonopy -o band.h5
```

Run `vibview --help` for all available commands and options.

## Configuration

Override hierarchy (later wins): package defaults → `~/.config/vibview/config.yaml` → `--config` session YAML → CLI overrides.

```yaml
# ~/.config/vibview/config.yaml
rendering:
  background_color: "#ffffff"
  atom_radius: 0.5

animation:
  fps: 30
  period: 2.0
```

See [defaults.yaml](https://github.com/kubrian/vibview/blob/main/src/vibview/data/defaults.yaml) for all keys and their defaults. Generate a commented template with `vibview init-config`.

## Documentation

- [Design & rationale](design.md)
- [API Reference](api.md)
