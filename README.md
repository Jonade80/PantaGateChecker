# Panta Gate Checker

Desktop application for repeatable Panta gate open/close endurance tests through Pandora's gRPC interface.

## Behavior

- Runs a user-selected number of gate cycles.
- Waits for Pandora's gate-state stream to confirm each operation.
- Polls the gate state every second and starts the next movement as soon as the gate arrives.
- Cancels 10% of open operations by default and verifies that the gate recovers to `CLOSED`.
- Stops on the first failed cycle.
- Creates a PDF summary with the device serial number, test name, operator name, cycle counts, and overall result.

Pandora must be running with gRPC enabled. Its normal endpoint is port `2316`.

## Setup

Python 3.9 and access to the NanoTemper package index are required.

```powershell
poetry install
poetry run panta-gate-checker
```

For local development:

```powershell
poetry run pytest
```

## Windows executable

Install Inno Setup once, then build the standalone executable and installer:

```powershell
winget install JRSoftware.InnoSetup
.\build_exe.ps1
```

Release artifacts are written to `dist`:

- `PantaGateChecker.exe`: portable standalone application
- `PantaGateChecker-Setup-0.1.0.exe`: per-user installer with Start menu and optional desktop shortcuts
- `SHA256SUMS.txt`: integrity checksums for both executables

The target computer does not need Python or Poetry installed.

## Product image

The Prometheus Panta image is sourced from the official NanoTemper product page:
https://nanotempertech.com/prometheus-panta/

Image (c) NanoTemper Technologies GmbH.