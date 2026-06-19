# Lyra Desktop Avatar

Transparent desktop avatar window for Lyra.

This module renders Lyra as a desktop companion, reads avatar state updates from the Python backend, and controls visual behavior such as expressions, blinking, pose changes, and lipsync.

## Running

In one terminal, start the Python backend:

```powershell
python main.py
```

In another terminal, start the Electron desktop avatar:

```powershell
cd desktop/electron
npm install
npm start
```

## Shortcuts

```text
Ctrl + Shift + L = toggle click-through mode
Ctrl + Shift + R = reload the avatar window
```

## Assets

The renderer uses a pose-based asset structure:

```text
assets/lyra/poses/
├── 01_idle_default/
│   ├── 01_idle_default.png
│   └── 01_parts/
│       ├── eye_closed.png
│       ├── eye_happy.png
│       ├── eye_open.png
│       ├── eye_serious.png
│       ├── mouth_closed.png
│       ├── mouth_middle_open.png
│       ├── mouth_open.png
│       ├── mouth_smile.png
│       └── mouth_surprise.png
├── 02_idle_shift/
│   ├── 02_idle_shift.png
│   └── 02_parts/
│       ├── eye_closed.png
│       ├── eye_happy.png
│       ├── eye_open.png
│       ├── eye_serious.png
│       ├── mouth_closed.png
│       ├── mouth_middle_open.png
│       ├── mouth_open.png
│       ├── mouth_smile.png
│       └── mouth_surprise.png
├── 03_idle_soft/
│   ├── 03_idle_soft.png
│   └── 03_parts/
│       ├── eye_closed.png
│       ├── eye_open.png
│       ├── eye_serious.png
│       ├── mouth_closed.png
│       ├── mouth_middle_open.png
│       ├── mouth_open.png
│       ├── mouth_smile.png
│       └── mouth_surprise.png
├── 04_thinking/
│   ├── 04_thinking.png
│   └── 04_parts/
│       ├── eye_closed.png
│       ├── eye_open.png
│       └── mouth_closed.png
├── 05_listening/
│   ├── 05_listening.png
│   └── 05_parts/
│       ├── eye_closed.png
│       ├── eye_open.png
│       ├── eye_serious.png
│       ├── mouth_closed.png
│       ├── mouth_middle_open.png
│       ├── mouth_open.png
│       ├── mouth_smile.png
│       └── mouth_surprise.png
└── 06_approach/
    ├── 06_approach.png
    └── 06_parts/
        ├── eye_closed.png
        ├── eye_open.png
        ├── eye_serious.png
        ├── mouth_closed.png
        ├── mouth_middle_open.png
        ├── mouth_open.png
        ├── mouth_smile.png
        └── mouth_surprise.png
```

All PNG layers must:

- use a transparent background
- keep the same canvas size as the base pose image
- remain aligned with the base pose
- be exported individually from the PSD or source file

## Avatar State

The desktop renderer reacts to the current Lyra state.

Expected states:

```text
idle
thinking
listening
speaking
approach
```

The Python backend updates the state file and the Electron renderer reads it to decide which pose, eyes, mouth, and animation should be active.

## Python to Electron Bridge

The current communication bridge uses:

```text
data/avatar/state.json
```

The Electron window watches this file and updates the avatar whenever the state changes.

## Notes

The desktop avatar no longer depends on VTube Studio.

All rendering, expression switching, and lipsync behavior are handled directly by this Electron module.
