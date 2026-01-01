# Geometry Dash Robot — Project Overview (Concise)

## What we’re building
A physical robot that plays **Geometry Dash** on a **tablet/phone** by physically tapping/holding the screen with a small actuator (“finger”). The system learns/improves by repeatedly running attempts on the real device and scoring progress using a camera feed (no game emulator/simulator).

## Hardware
- **Host computer:** Ubuntu desktop (main “brain” running Python)
- **Microcontroller:** Raspberry Pi **Pico** (real-time executor)
- **Actuator:** SG90 servo + capacitive stylus tip (finger)
- **Camera:** USB webcam connected to host
- **Game device:** tablet/phone running Geometry Dash
- **Rig:** tablet + webcam mounted in a **K’nex structure** for reproducible alignment

## Core idea: binned instruction scripts
Gameplay input is represented as a binary array:
- `bins[i] ∈ {0,1}` over fixed `bin_ms` (currently ~75ms)
- `0` = finger up (no press)
- `1` = finger down (press/hold)
This representation supports taps and holds naturally.

---

# System Architecture (4 Modules)

## 1) Clicker (Pico + host client)
**Purpose:** Execute scripts deterministically as servo motion.
- **Input:** `Script = {bin_ms, bins[], optional_preamble}`
- **Output:** Physical taps/holds on screen + serial acknowledgements
- **Runs on:** Pico firmware (MicroPython)
- **Host side:** Python serial client sends scripts/commands.

**Protocol:** USB serial (line-based)
- Host → Pico: `PING`, `LOAD`, `DATA`, `START`, `STOP`
- Pico → Host: `PONG`, `LOADED`, `STARTED`, `DONE`, `STOPPED`, `ERR`
**Why:** Pico provides real-time timing; avoids OS jitter.

## 2) Monitor (host)
**Purpose:** Observe tablet via camera and compute scoring + end-of-run.
- **Input:** Webcam frames + `start_run(run_id, config)`
- **Output:** Events emitted to orchestrator via an in-process `Queue`
  - `HeartbeatEvent(run_id, fps, ts)` (1 Hz)
  - `ProgressEvent(run_id, score, ts)` (optional / throttled)
  - `EndEvent(run_id, final_score, reason, ts)`

**End detection:** (both, debounced)
- **Green-screen detector** (end UI)
- **Motion-stopped detector** (low frame-diff energy)
Monitor owns score computation (orchestrator does not inspect frames).

## 3) Trainer (host)
**Purpose:** Generate improved scripts from history.
- **Input:** last N runs (scripts + scores) from storage
- **Output:** next `Script` to try
Initial version: greedy/mutation-based; later can keep a small population.

## 4) Orchestrator (host)
**Purpose:** Command center for `run` and `train` modes.
- **CLI:**
  - `robot run --level <level_name>` (inference)
  - `robot train --level <level_name>` (training loop)
- **Responsibilities:**
  - Loads best script from disk, sends to clicker
  - Starts monitor and listens for events
  - On EndEvent or timeout: stops clicker, logs run, updates history
  - Calls trainer to get next script in training mode
  - Enforces **timeouts** to avoid hangs
  - Uses `run_id` everywhere to avoid stale/mixed events

---

# Communication Patterns
- **Host ↔ Pico:** USB serial protocol (batch scripts)
- **Monitor → Orchestrator:** `Queue[Event]` (heartbeat/progress/end), tagged with `run_id`
- **Orchestrator ↔ Trainer:** direct function/class calls

---

# Storage / Logging (host disk, per level)
Directory layout:
- `data/levels/<level>/runs.jsonl` — append-only run results  
- `data/levels/<level>/scripts/<script_id>.json` — scripts tried  
- `data/levels/<level>/logs/<run_id>.log` — per-run event trace  
- `data/levels/<level>/best.json` — best script pointer (id + score)

**Why JSONL:** robust to crashes, easy to tail last 100 runs.

---

# Training Loop (how improvement happens)
1. Orchestrator loads current best script (or seed/random).
2. Clicker executes on tablet; monitor scores and detects end.
3. Orchestrator logs run result + updates best if improved.
4. Trainer proposes next script (mutation/optimization).
5. Repeat until convergence.

Goal: autonomously improve scripts to complete harder levels on real hardware.
