## Geometry Dash Robot

This project is for a robot that plays Geometry Dash (a childhood classic). It controls a physical robot “finger” (servo + stylus) to click on a real phone/tablet.

A host computer sends scripts over USB serial to a Raspberry Pi Pico which performs deterministic taps/holds.

### CLI

The CLI entrypoint is `robot` (see `pyproject.toml`).

#### Install Pico clicker firmware

Uploads the MicroPython clicker files to the Pico via `mpremote` and resets the device:

```bash
robot clicker install --port /dev/ttyACM0
```

If you omit `--port`, the tool will try to auto-detect a Pico serial port.

#### Run a script (inference)

Runs a specific saved script for a level:

```bash
robot inference --level stereo_madness --script-id hand_coded_v0 --port /dev/ttyACM0
```

Options:
- `--baud` (default `115200`)
- `--port` (auto-detected if omitted)

The command prints a `run_id` on success and logs a run record under `data/levels/<level>/`.

#### Train (stub)

```bash
robot train --level stereo_madness
```

This currently raises `NotImplementedError`.

### Data layout

- `data/levels/<level>/scripts/<script_id>.json`: input scripts (`bin_ms` + `bins[]`)
- `data/levels/<level>/runs.jsonl`: append-only run results
- `data/levels/<level>/logs/<run_id>.log`: per-run logs
