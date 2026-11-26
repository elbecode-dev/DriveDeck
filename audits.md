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
| 1 | No `Accessible.*` anywhere in the QML (cards, `QuickBtn`, `WinBtn`, temperature chips). | ✅ (2.0.0) | `WinBtn` (rc4); in 2.0.0 also `QuickBtn`, folder/drive/network/printer cards, temperature chips, live chips and the ink bars (role plus localized name with free space, temperature, status). Not yet tried with a real screen reader. |
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

## 5a. Regressions found after release (rc4 → rc5)

| Finding | Status | Change |
|---------|--------|--------|
| **Live chips and I/O graph hidden after start (rc4).** The new `fensterAktiv` property was not yet updated when `onVisibilityChanged` read it, so the backend was told "not visible" at start and its loops stayed paused until the window was maximized. Reproduced offscreen (window `Windowed`, backend inactive, no stats). | ✅ rc5 | The handler computes the state directly from `win.visibility`; the property remains for the animations. |
| **31 `pyright` errors** after a system update: the PyQt6 6.12.1 stubs wrongly require the keyword `arguments` in `pyqtSignal(...)`. | ✅ rc5 | `pyqtSignal = cast(Any, pyqtSignal)` with a comment; no runtime effect. |

Lesson: a derived property must not be read in a change handler of the property it derives from. The offscreen harness now checks that the backend is active after start.

---

## 5b. v2.0.0 polish pass

Two passes, the second one (design review with the *qt-ui-engineering* skill and the Apple HIG notes) replaced parts of the first.

| Item | Status | Change |
|------|--------|--------|
| Card containers | ✅ replaced | A first pass put a permanent box with a 1 px outline behind every card. It cost text width ("… frei von …" got cut) and looked heavy, so it was removed again. Cards float freely; a new `GlassHover` (faint fill, 150 ms `OutCubic`, hairline light edge on the top only, `radius: 10`) appears on hover or keyboard selection. `CardGlow` (violet-blue-cyan) stays for the live panel. |
| Mount status | ✅ | 6 px dot before the status text (green = mounted, grey = unmounted); metadata of unmounted drives at 0.72 opacity. |
| Usage bars | ✅ | 4 px pills with a fine track (8 % white/black) and a gradient: blue/cyan, amber from the warning threshold, coral from halfway between threshold and full. |
| Tabular figures | ✅ | `infoFontT` (via `Qt.font({ features: { "tnum": 1 } })`, because `font: x` cannot be combined with `font.features`) and `font.features` on temperatures, rates, percentages and live values. |
| I/O graph spacing | ✅ | Card padding back to 8 px: the graph keeps 8 px to the card edge. |
| Ink pills | ✅ | 8 × 40 px, `radius: 4`, glass track, no box (a first 4 × 22 px version was too small to read); red pulsing outline below 15 % (gated by `fensterAktiv`); tooltip and "no values" hint kept. |
| Ribbon | ✅ | Icons rest at 0.72 opacity and go to 1.0 on hover; disabled at 0.42; title bar and ribbon alpha 0.74 → 0.90 with blur. The first idea, desaturating the icons with `MultiEffect`, was dropped: shader effects do not render with the software scene graph (icons vanished in the offscreen test) and could hide the toolbar on VMs. |
| Blur readability | ✅ | `glassBody` 0.86 → 0.93. |
| Sidebar | ✅ | Pinned entries 0.22 at rest, 1.0 on row hover (120 ms); selection pill `radius: 6`, outline and stronger tint kept also when the main area has the focus. |
| Accessibility gap 5.1 | ✅ | See the status above. |

**Checks:** `pyright` 0 errors, `qmllint` clean, 1500 random state changes (drive lists, printers with 0–6 cartridges at 0–100 %, minimise, resize, mouse movement, temperatures) with 0 runtime warnings, startup check (backend active and stats arriving after 3 s). Visual check by offscreen screenshot only; there the scheme reports as dark while the window paints light, so the hover glass could not be judged. Real Plasma light and dark schemes, real KWin blur and a real screen reader remain unverified. A "hole" in the ribbon under *Aktionen & Werkzeuge* and *System-Zentrale* could not be reproduced offscreen (no blur there); the ribbon fill is one rectangle over the full width, and its opacity was raised to make the surface calmer.

---

## 5c. Typography pass (v2.0.0)

| Item | Status | Change |
|------|--------|--------|
| Font stack | ✅ | `schriften_aufloesen()` checks `QFontDatabase.families()` for "Inter" and "JetBrains Mono" (both OFL; nothing bundled, no proprietary fonts referenced). Inter becomes the application font; QML exposes `win.uiFont` and `win.monoFont` (fallback: `Kirigami.Theme.defaultFont`, then `monospace`). |
| Hierarchy | ✅ | Window title and section headers DemiBold with tracking −0.25 / +0.6; card titles DemiBold; details regular at the system size. First version used 92 % for details; it read too small and too wide, so sizes are back at 100 %, tracking is −0.12 px and hinting is off (`PreferNoHinting`) for smoother outlines. JetBrains Mono values at 95 %; temperature chips without the space (`44°C`) because a mono space is a full cell. |
| Telemetry | ✅ | JetBrains Mono plus `tnum` for temperature chips, I/O rates, live chip values and the uptime/installed/kernel lines. |
| Clipping check | ✅/➖ | Screenshots at 1300 and 2000 px: titles, ribbon, live panel and normal free-space texts fit. A card that also shows the "almost full" pill can still cut the free-space text (as before); it now shows the full text as a tooltip. |

**Checks:** `pyright` 0 errors, `qmllint` clean, 1500 random state changes with 0 runtime warnings, startup check passed. Not tested: a system without Inter or JetBrains Mono (the fallback path is only code-reviewed), and other languages with longer texts.

---

## 5d. Floating glass sidebar (v2.0.0)

| Item | Status | Change |
|------|--------|--------|
| Glass panel, spotlight, no footer | ✅ | `sidePanel` (`radius: 14`, 8 px margin left/top/bottom, faint fill, hairline outline) replaces the hard divider; a `RadialGradient` spotlight (max 4 %) follows the mouse and is off when `!win.fensterAktiv`. The footer status bar is removed; the content area now reaches the window edge with rounded bottom corners (`RoundedBar`). |
| Header card | ✅ | App icon (36 px), window name, version pill (`aboutInfo.version`), status dot with "This PC · N items" (new `itemCount` property, same count as the old footer; translations "1 item" / "{n} items"). |
| Section headers and rows | ✅ | Capitals at 85 % size with tracking +0.6, no heading icons, hover pill on "+", row pills `radius: 8` with the new `SpecEdge` (top light edge), pin icons 0.18 → 1.0. |
| Drive rows | ✅ | Mounted drives: 3 px bar (accent, amber from the warning threshold), size in JetBrains Mono with `tnum`, eject button on hover for removable media (`backend.ejectDevice`, accessible name set). Unmounted drives: extra dimmed rows (0.48) without a path, so opening, pinning and tree expansion do nothing for them (`toggleNodeNow` ignores an empty path). |
| Header duplicate | ✅ | With a custom name "Dieser PC" the card showed it twice (title and status). The status line drops "This PC" when the title already says it. |
| Not done | ➖ | A third "LAUFWERKE" heading (drives stay under "Dieser PC"); a coloured media icon for the "OnAir" pin (pin icons come from the backend, a name-based mapping would be a hack). |

**Finding during testing:** with the new rows the stress test sometimes ended with Qt's "There are still N items in the process of being created at engine destruction". Cause: the sidebar `ListView` pre-creates delegates outside the visible area (`cacheBuffer`) and some were unfinished at exit. `cacheBuffer: 0` fixed it (0 of 6 runs affected, before about 2 of 4); the gliding `displaced` animation was not the cause and stays. A custom `background` on the "+" `ToolButton` hid its icon (the desktop style draws the icon in the background), so the hover pill is a separate rectangle.

**Checks:** `pyright` 0 errors, `qmllint` clean, 1500 random state changes including arrow keys, Return, Space and mouse movement over the sidebar with 0 runtime warnings (3 runs), startup check passed. Visual check by offscreen screenshot only (light window, dark-scheme flag), so the glass fill and the version pill could not be judged; real Plasma schemes, KWin blur and the eject action with a real device are unverified.

---

## 5e. Post-release check (after 2.0.0, limited to 30 minutes)

| Check | Result |
|-------|--------|
| Soak test, 12 min, 80 000 random actions (drive and printer lists, minimise, resize, mouse, arrow/Tab/Home/End/Esc keys, temperatures, threshold) | No crash (`faulthandler` empty), 0 Qt/QML messages, memory 171–190 MB without upward trend (179 MB at the end). |
| Idle CPU, real data, offscreen | 1.05 % over 60 s (rc3: 1.2 %). No GPU in this measurement. |
| `qt-qml-review` lint rules | 348 notes, almost all style (property order, `var`, group notation); no binding or crash findings. |
| Code review of the changes since rc5 | Two real bugs, both fixed: (1) the window buttons were focusable but the program's own Tab handling never let focus reach them, so the rc4 claim "reachable with Tab" was wrong; Tab now cycles main → sidebar → buttons → main, Shift+Tab backwards, Esc returns (checked with a key sequence test). (2) An empty optical drive showed the green "mounted" dot; it is grey now. |
| Not done | `qmlprofiler` run (setup did not fit the time limit). |

---

## 5f. Inspector panel and toolbar pass (after 2.0.0)

| Item | Status | Change |
|------|--------|--------|
| Inspector, system overview | ✅ | Right glass panel (`radius: 14`, 8 px margin right/top/bottom, hairline edge), shown from 1280 px. Hero tile with logo, host, OS, kernel, Plasma, uptime, install date; four `LiveCard`s with `Spark` sparklines (60 s history kept in QML, only collected while the inspector is visible and the window is not minimized). |
| Inspector, details | ✅ | `inspectorItem` follows `selectedKey` (folder, drive, network location, printer/device). Key/value rows, ink levels with bars, action buttons (`focusPolicy: Qt.NoFocus`, so the arrow keys stay with the main area). Clicks inside the inspector no longer clear the selection. |
| Not available | ➖ | No UUID and no printer driver: the backend does not read them. Instead the device path and, new in the printer data, the CUPS/eSCL address (credentials in the URI are stripped). |
| Toolbar | ✅ | `showInfo`/`showPanel` are off while the inspector is visible; below 1280 px the ribbon keeps its info block and telemetry (with their accessible names). |
| Sidebar header, section hairlines, drive-row overlap, scanner names | ✅ | Turquoise-blue gradient and cyan badge with dark text; solid 1 px hairline; drive rows use the full width and the size label keeps its minimum width; `scanner_anzeigename()` turns eSCL source lists into "(Flatbed & ADF)". |

**Finding during testing:** the first `Spark` was a `Shape` inside a layout; its implicit width followed the path, which produced a "Binding loop detected for property path" warning 1296 times in the stress test. Wrapping the `Shape` in an `Item` fixed it (0 messages afterwards).

**Checks:** `pyright` 0 errors, `qmllint` clean, 100 s stress test (10 000 actions incl. window sizes with and without inspector, keyboard selection changes) with 0 messages and no crash, click test (a click in the inspector keeps the selection). Visual check on the real desktop (dark scheme, blur) via the new preview; light scheme not checked.

---

## 5g. Final 2.0.0 polish: toolbar opacity and Breeze Light check

| Item | Status | Change |
|------|--------|--------|
| Ribbon opacity | ✅ | The title bar and ribbon fill is one rectangle over the full width; a screenshot showed identical pixels from left to right. The brighter look on the right came from the wallpaper behind it at 90 % alpha. Raised to 95 % with blur so it no longer shows. |
| Breeze Light check | ✅ | Switched the Plasma scheme to Breeze Light with `plasma-apply-colorscheme`, took real screenshots, switched back to the user's scheme (`VividVioletDarkColorscheme`, verified with `kreadconfig6`). |
| Bug found: light schemes treated as dark | ✅ | `themeProbe` (the item behind `win.darkTheme`) was `visible: false`. Kirigami gives invisible items no scheme colours (background `#000000`), so `darkTheme` was always true: in light schemes glass panels and cards used white edges (invisible), count badges used light text, and the cyan sparkline used the light-on-dark variant. Fixed with a visible zero-size probe (verified: background now `#182030` in the dark scheme, light variants in Breeze Light). This also explains why earlier offscreen checks reported "dark" for a light window. |
| Light contrast | ✅ | Glass outlines in light schemes 0.08 → 0.13 (panels) and 0.07 → 0.12 (cards), card fill 0.03 → 0.045, section count text darker accent. The cyan `2.0.0` badge with dark text reads well in both schemes. |

**Checks:** `pyright` 0 errors, `qmllint` clean, 90 s stress test (8000 actions) with 0 messages and no crash, Tab cycle test passed.

---

## 5h. System details in the inspector header (after 2.0.0)

| Item | Status | Notes |
|------|--------|-------|
| CPU/GPU names | ✅ | Read once in the background thread that also reads the Plasma version: `/proc/cpuinfo` (shortened to e.g. "Ryzen 9 5900X"), GPU via `nvidia-smi` or `lspci -mm` (dedicated card first, shortened to e.g. "RTX 4080 SUPER"). |
| Temperatures | ✅ | CPU sensor path found once in `/sys/class/hwmon` (Tctl/Tdie/Package label preferred) and read every second in the existing stats loop; GPU from an `amdgpu`/`nouveau`/Intel hwmon sensor, otherwise `nvidia-smi` every 15 s. Rounded to whole degrees so the UI only updates when the shown value changes. |
| Scheduler, IP, session | ✅ | `/sys/kernel/sched_ext/state` + `root/ops` every 5 s ("bpfland_1.1.4_…" → `scx_bpfland`), otherwise EEVDF (kernel ≥ 6.6) or CFS; IPv4 via a UDP socket "connect" to TEST-NET (sends nothing) every 30 s; `XDG_SESSION_TYPE` once. |
| Updates | ✅ | Own background thread: 10 s after start, then every 2 h; `checkupdates` exit code 0 = list, 2 = none, anything else ignored; skipped silently if the tool is missing. |
| Robustness | ✅ | Each read is wrapped; an error only drops that value and never stops the telemetry loop. |
| Idle CPU | ✅ | Offscreen, 60 s after the first update check, compared with the previous commit: DriveDeck itself 1.33 % → 1.60 %, helper processes 0.31 % → 0.37 %. A first version (unrounded temperatures, `nvidia-smi` every 5 s) cost 1.78 % + 0.62 % and was tuned down. |

**Checks:** `pyright` 0 errors, `qmllint` clean, 60 s and 45 s stress tests with 0 messages and no crash, real-data screenshot of the header card (Ryzen 9 5900X · 43 °C, RTX 4080 SUPER · 42 °C, scx_bpfland, IP · Wayland, "3 Updates").

---

## 5i. Ribbon balance, live filter, inspector toggle (after 2.0.0)

| Item | Status | Notes |
|------|--------|-------|
| Centred groups | ✅ | Stretchable spacers left of the groups and right of "System center" (only while the inspector is visible); `sysGrp` is limited to its buttons then. The ribbon width now uses the row's `implicitWidth` instead of `sysGrp.x` (no dependency on its own layout). `sideWidth` subtracts the left spacer, so the sidebar does not grow. Measured on a 2000 px offscreen screenshot: about 68 px space on the left, about 110 px between "Info" and the filter. |
| Live filter | ✅ | `filterText` drives `fFolders`/`fDisks`/`fNets`/`fPrinters`; the four `Repeater`s, section counts, `itemCount` and `navSections()` use the filtered lists, so the arrow keys never land on hidden cards. Matches the name plus type text (file system, status, "usb", "cd dvd", path). |
| Inspector toggle | ✅ | `inspectorWanted` (not saved between starts); button with accessible name and `Ctrl+I`. |
| Limitation | ➖ | With the inspector hidden on a wide window, the filter area takes room from "System center": at 2000 px the info block and telemetry chips no longer fit into the ribbon (they need about 2200 px). Below 1280 px nothing changed: no filter, no toggle, the ribbon scrolls and shows info/telemetry as before. |

**Checks:** `pyright` 0 errors, `qmllint` clean, scripted test (Ctrl+F, typing "usb" → 4 items, Esc → filter empty and 13 items, Ctrl+I → inspector hidden, resize to 1100 px → narrow layout), 60 s stress test with 0 messages and no crash, Tab cycle test unchanged. One scripted run aborted, but that was a bug in the test script (an exception inside a PyQt timer callback), not in DriveDeck.

---

## 6. Not verified

These need a real desktop session and were **not** covered by the offscreen tests:
- Contrast ratios were judged on real screenshots (dark scheme and Breeze Light), not measured with a contrast tool.
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