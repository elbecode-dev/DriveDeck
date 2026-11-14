# Audits – DriveDeck

Summary of the quality audits run on DriveDeck during the 2.0.0 release-candidate phase (rc1 to rc4): what was tested,
what was found, what was changed, and what could **not** be verified. Line numbers refer to `drivedeck.py` at the time of
the audit and move with every edit.

Status legend: ✅ fixed · ⏳ open · ➖ intentionally left as is

---

## 0. Static Type, Null-Safety & Launcher Audit (rc1–rc2)

**Goal:** eliminate static type errors, protect background telemetry against unexpected `None`/sensor failures, and harden desktop launcher integration.

| # | Finding | Status | Change |
|---|---------|--------|--------|
| 1 | **87 Pyright errors** across the Python backend (untyped module states, missing return annotations, dynamic attributes on Qt roots, optional `NumPy` imports). | ✅ | Reduced `pyright` issues from **87 to 0** (Standard Mode) via explicit typing, `HAS_NUMPY` guards, and `cast(QWindow, ...)`. |
| 2 | **SMART worker thread crash** when `smartctl` variants returned `None` on `stdout`. | ✅ | Added explicit `r.stdout` null-guards; failed queries return a localized fallback message instead of aborting the thread. |
| 3 | **Single-sensor failure aborting temperature loop:** an unreadable sensor on one disk stopped evaluation for subsequent drives. | ✅ | Isolated per-drive assignments inside local `try` blocks during sensor polling. |
| 4 | **Qt singleton null-safety:** `rootContext()`, `clipboard()`, `primaryScreen()`, `styleHints()`, and `nextPendingConnection()` could return `None` during display transitions. | ✅ | Guarded all singleton calls with safe helpers (e.g., `_in_zwischenablage()`). |
| 5 | **Launcher sync & rapid renames:** custom names missed desktop `.desktop` copies, were overridden by `Name[xx]=`, raced on rapid edits, or tried writing to `/usr` on system-wide installs. | ✅ | Queue-serialised launcher updates (with resume on interrupted exit), stripped `Name[xx]=`, synced all `drivedeck*.desktop` shortcuts, created local overrides under `~/.local/share/applications/` for `/usr` installs, and refreshed `kbuildsycoca6`. |
| 6 | **Version precedence & dialog overflow:** release candidates did not rank strictly above beta builds; long mount/device strings clipped at higher font scales. | ✅ | Fixed release ordering (`alpha < beta < rc < final`) and enforced `Text.ElideRight` with full hover tooltips in properties dialogs. |

---

## 1. Chaos / stress audit (rc3)

**Goal:** break the program with rage-clicking, hung or vanishing devices, extreme scaling, corrupted state and abrupt exits.

| # | Finding | Status | Change |
|---|---------|--------|--------|
| 1 | **Lost saves.** `schreibe_atomar()` used one shared `.tmp` file; simultaneous writers made saves fail (908 of 2400 in the stress test). | ✅ | Unique temp file per write (`tempfile.mkstemp`) plus a lock, `fsync`, `os.replace`, cleanup on error. |
| 2 | **Leftover temp files** after a hard abort (`kill -9`). | ✅ | `alte_temp_dateien_entfernen()` removes stale `.tmp` files at the next start. |
| 3 | **Rage-clicking** a launcher spawned dozens of processes (file manager, terminal, …). | ✅ | `lancer()` ignores an identical launch within 1 s. |
| 4 | **Check-then-act races** on "already running" sets (usage probe, SMART temperature, TRIM): two threads could pile up on the same dead mount or disk. | ✅ | Locks `_USAGE_SPERRE`, `_TEMP_SMART_SPERRE`, `_TRIM_SPERRE`. |
| 5 | **Trash scan** time limit did not apply while reading very large sub-folders. | ✅ | The limit is checked every 500 entries inside sub-folders too. |

**Results after the fixes**
- 2400 concurrent writes: 0 errors.
- 15 × `kill -9` during writes: 0 corrupt files; orphaned temp files cleaned at the next start.
- 4000 clicks per run on the UI: no QML warnings.

**Incident.** An early version of the test harness launched real Dolphin, Filelight and Konsole through `lancer()` and
brought the desktop session down (dbus-broker died). Since then every harness stubs `lancer` and blocks all launching
subprocesses (`pkexec`, `udisksctl`, `umount`, `eject`, `lp`, `lpoptions`, `fstrim`, `kwallet-query`, `smbclient`,
`update-desktop-database`, `kbuildsycoca6`). The log line
`dbus-broker-launch: Ignoring duplicate name 'org.freedesktop.FileManager1'` that showed up in the crash log is unrelated:
several file managers (nemo, dolphin, generic) ship a service file for the same name.

---

## 2. Performance and memory audit (rc3)

**Method:** `QT_QPA_PLATFORM=offscreen` harness, process and CPU sampling, and `qmlprofiler` (enabled for PyQt through
`QQmlDebuggingEnabler::enableDebugging` via `ctypes` and a wrapper script, trace parsed with the profiler plugin script).
The standalone report is in `profiler/reports/` (not part of the repository).

**Measured**
- Idle CPU: about **1.2 %**.
- Memory: **no leak** over the test runs; no rendering jank in the profile.
- At start the QML engine created roughly 330 `MenuItem` and 490 `Label` objects, mostly from context menus that were built eagerly.

| # | Finding | Status | Change |
|---|---------|--------|--------|
| 1 | `lpstat -v` ran a second time in every printer cycle (about 11 extra processes per minute). | ✅ | Output cached for 10 s (`_LPSTAT_V`) and shared by `list_printers()` and `cartes_scanners()`. |
| 2 | `xdg-user-dir` queried twice per folder type at start. | ✅ | Memoised once per type (`_XDG_DIRS`). |
| 3 | 7 context menus built eagerly (see counts above). | ✅ (rc4) | `LazyMenu` (a `Loader` with `active: false`) builds each menu on first use. |
| 4 | Settings, section state and window size written with `fsync` in the GUI thread, at every slider step. | ✅ (rc4) | One write 300 ms after the last change, plus a flush at exit. Test: 25 slider steps and 50 resize/section changes gave 0 immediate writes and one write per file afterwards. |
| 5 | Endless pulse animations kept running while the window was minimized. | ✅ (rc4) | `running:` now also requires `win.fensterAktiv`. |

---

## 3. Stability and UI/UX review (rc3)

- Temperature chips were not aligned between mounted and unmounted drive cards → ✅ placeholder item in the name row of unmounted cards (a full-width placeholder had truncated the status text and was replaced).
- Static checks with `pyright`: 0 errors, 0 warnings.

---

## 4. UI engineering review (theming and UX)

Review with the *qt-ui-engineering* skill (UI review checklist, colour system, accessibility, desktop UX). Two major
findings came out of it and were handled in the full audit below: missing accessible names and fixed, non-theme-aware colours.

---

## 5. Full code, UI and function audit (rc4)

Read-only audit first, then a selected set of fixes. Scope: function and interaction integrity, dead code, QML
performance, architecture and thread safety, static analysis and runtime warnings.

### What was checked and found clean
- **Static:** `pyright` 0 errors; `qmllint` on the exported QML (`python drivedeck.py --dump-qml`) reports nothing.
- **Handlers and slots:** all 61 `backend.*` calls in the QML point to existing Python members with matching argument counts. No unused slot, no unused import, no function that is defined but never called (AST scan).
- **Runtime:** 1500 random state changes (drive list with 0–14 entries, long names and mount points, health `warn`/`fail`, threshold changes, renames, minimise/maximise, empty network/printer/temperature/I/O signals) produced **0** `ReferenceError`, `Binding loop` or `Unable to assign` messages. The message handler was proven working with a test message.
- **Races:** usage probe, SMART temperature, TRIM and `schreibe_atomar()` run under locks; SIGTERM/SIGINT are handled in `main()` and shut down in order.
- **Title-bar hit boxes:** `WinBtn` and the rename pencil have their own `MouseArea`; the drag and tap handlers sit on the bar.

### Findings and status

**Critical**

| # | Finding | Status | Change |
|---|---------|--------|--------|
| 1 | No `Accessible.*` anywhere in the QML (cards, `QuickBtn`, `WinBtn`, temperature chips). | ⏳ partly | `WinBtn` now has role and name. Cards, `QuickBtn` and chips are still open. |
| 2 | Window buttons not reachable by keyboard; 16 px target. | ✅ | Tab focus with a focus ring, Enter/Space, accessible names; the hit area is 24 × 24 px (`margins: -4`), the visible dot stays 16 px. |
| 3 | Almost no global shortcuts (only `handleKey`: F5, Tab, arrows, Enter, Space, Escape, Home/End, Ctrl+C). | ✅ | `Ctrl+Q` (quit through `close()`, so the window size is saved) and `F2` (rename). Both use `Qt.ApplicationShortcut`: with the default window context they did not fire in the offscreen test. |
| 4 | Fixed colours with too little contrast: cyan sparkline 2.4 : 1 on light backgrounds, warning triangle about 2 : 1, health text `#c42b1c`/`#d35400` 2.7 : 1 and 3.7 : 1 on dark. | ✅ (not measured) | Colours derive from `Kirigami.Theme` and are darkened or lightened by scheme; `gaugeBlue` follows the accent colour (falls back to the fixed blue for reddish accents), `gaugeRed` the negative colour; fixed fallbacks when Kirigami returns black. **Contrast on a real Plasma light/dark scheme has not been measured.** |
| 5 | "Storage" and "Network" in the live chips were not translated. | ✅ | `win.trad(...)`; "Storage" added to `EXTRA_DE`. |

**Optimisation**

| # | Finding | Status |
|---|---------|--------|
| 1 | GUI-thread `fsync` saves at every slider step | ✅ debounced |
| 2 | Eager context menus | ✅ lazy |
| 3 | Endless animations while minimised | ✅ gated by `fensterAktiv` |
| 4 | 16 layout literals off the Kirigami grid (radii 4449/5886/6884/7325/7644, spacings 4451/5779/5879/6007/…) | ➖ most are deliberate 1–2 px details; real candidates (5779, 5879, 6007, 7325, 5886) still open |
| 5 | Fixed hex colours for gauges and traffic-light buttons | ✅ gauges themed · ➖ traffic lights are branding |
| 6 | Ribbon scrolls horizontally with no hint (the documented 1990/1710/1220 px breakpoints do not exist in the code; minimum window 800 × 520) | ⏳ idea: edge fade or arrows |
| 7 | Hard-coded button widths (`minW` 84–104) do not scale with font size or longer translations | ⏳ no clipping seen at 150 % |

**Clean-up**

| # | Finding | Status |
|---|---------|--------|
| 1 | Unused QML `id: titleBar` | ✅ removed |
| 2 | Mixed French/German comments | ➖ cosmetic |
| 3 | Duplicated card code (drive delegate vs. network/printer delegate, identical "almost full" blocks, three identical ribbon separators) → shared `DeviceCard` | ⏳ deliberately postponed (large refactor) |
| 4 | `profiler/` untracked in the repository folder | ✅ in `.gitignore` |

### Exit race
Once, a test run ended with `imprimantes : wrapped C/C++ object of type Backend has been deleted`: a background loop emitted a
signal while the backend was already being torn down. In the loops that emit to the backend (temperature, I/O, drives ×2,
network, printers) the error message is now suppressed once `_ENDE` is set. This silences the message; it does not stop
the thread from emitting. 3 further runs before and after the change showed no recurrence, so the race itself is rare enough
that it could not be triggered on purpose.

---

## 6. Not verified

These need a real desktop session and were **not** covered by the offscreen tests:
- Real Plasma **dark colour scheme** (the offscreen platform does not apply it; the contrast values are therefore unmeasured).
- Real pointer behaviour: drag, resize at the window edge, hover and hit-testing, double click on the title bar buttons.
- Screen readers (Orca) and the real Tab order.
- GPU overdraw and GPU load.
- Memory behaviour over many hours.
- The context menus of the drive, network and printer cards were only exercised by right-click scans (no warnings), not inspected visually. The export menu could not be opened because its dialog was closed.

---

## 7. How the tests were run

All harnesses set `QT_QPA_PLATFORM=offscreen`, `DRIVEDECK_NOBLUR=1`, `DRIVEDECK_MULTI=1`, patch `QApplication.exec`, capture QML
warnings with `qInstallMessageHandler`, stub `lancer`, and wrap `subprocess.Popen` to block privileged and launching
commands. Screenshots use `grabWindow().save()`. The exported QML (`python drivedeck.py --dump-qml`) maps to `drivedeck.py`
as: file line = dumped line + 4347 (at the time of the audit).