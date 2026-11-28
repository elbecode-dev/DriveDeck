# Audits – DriveDeck

Summary of the quality audits run on DriveDeck during the 2.0.0 release-candidate phase (rc1 to rc4) and after the
2.0.0 release (5e–5o): what was tested,
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
| Card containers | ✅ replaced | A first pass put a permanent box with a 1 px outline behind every card. It cost text width ("… free of …" got cut in the German UI) and looked heavy, so it was removed again. Cards float freely; a new `GlassHover` (faint fill, 150 ms `OutCubic`, hairline light edge on the top only, `radius: 10`) appears on hover or keyboard selection. `CardGlow` (violet-blue-cyan) stays for the live panel. |
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
| Header duplicate | ✅ | With a custom name equal to the default heading ("This PC") the card showed it twice (title and status). The status line drops "This PC" when the title already says it. |
| Not done | ➖ | A third "Drives" heading (drives stay under "This PC"); a coloured media icon for the "OnAir" pin (pin icons come from the backend, a name-based mapping would be a hack). |

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

## 5j. Full-height side panels (after 2.0.0)

| Item | Status | Notes |
|------|--------|-------|
| Layout | ✅ | The root `ColumnLayout` (title, ribbon, content) now has left/right margins `leftColW`/`rightColW`; sidebar and inspector moved out of the content area to window level and run top to bottom. One window background (`radius: win.cornerR`, View colours) replaces the separate title, ribbon and content fills, so there is no double alpha in the middle. |
| Window buttons | ✅ | One `winBtnRow` whose `parent` switches between the inspector header and the title bar; ids and the Tab cycle (main → sidebar → buttons → main) unchanged and re-tested. |
| Window move | ✅ | Drag/double-click on the title bar as before, plus on the sidebar header card and the inspector header. |
| Filter removed | ✅ | Filter field, `Ctrl+F` and the filter logic are gone; the main area lists (`fFolders` … `fPrinters`) are plain lists again. |
| Telemetry never disappears | ✅ | Without the inspector and without room for the ribbon telemetry, a compact mono line (CPU, RAM, network) with a system tooltip sits at the left of the title bar. |
| Trade-off | ➖ | The middle column is narrower than the old full-width ribbon: at 1600 px with both panels the ribbon scrolls (it fits from roughly 2300 px). The sidebar width is fixed (330 px × font growth) instead of following the first ribbon separator. |

**Checks:** `pyright` 0 errors, `qmllint` clean, scripted layout test at 1600 px (inspector on and off via Ctrl+I) and 1024 px, Tab cycle test, 60 s stress test with 0 messages and no crash.

---

## 5k. Default file manager (after 2.0.0)

| Item | Status | Notes |
|------|--------|-------|
| Hard-coded Dolphin | ✅ | Reported by the user: "Open with Dolphin" ignored the default file manager (here a custom "File Explorer"). `standard_dateimanager()` reads `inode/directory` from the XDG `mimeapps.list` chain (desktop-specific and general files, config before data dirs, Flatpak exports included) without starting a process; `exec_argumente()` turns the `Exec` line into arguments (`%u/%U/%f/%F` → path, other field codes dropped). Local folders open with that program; network URLs keep the Dolphin/`xdg-open` path. Menu label and icon come from the `.desktop` file. Checked: user's config → "File Explorer" with `/home/…/file-explorer %U`; without user config → system default Dolphin. |
| Default terminal | ✅ | `standard_terminal()` (cached, only files and `PATH`): `xdg-terminal-exec` → `kdeglobals` `[General]` `TerminalApplication`/`TerminalService` → `$TERMINAL` → konsole, kitty, alacritty, foot, wezterm. `_TERMINAL_ARTEN` maps each known terminal to its working-directory option and its way to run a command; unknown terminals get `-e` and the process `cwd`. Used by "Open in terminal" and by `terminal_befehle()` (terminal tools such as btop). Checked on this system: KDE default kitty → `kitty --directory <dir>`, label "Open in Kitty terminal", icon `kitty`; with `$TERMINAL=alacritty` and no KDE config → alacritty; without both → konsole. Actually launching a terminal was not tested (the harness blocks launches). |

---

## 5l. Full end-to-end audit (after 2.0.0)

Scope: typography, contrast and spacing on the real desktop; every 2.0.0 feature (default file manager and terminal,
inspector modes A and B, optical drives, pins, keyboard and screen reader); static analysis and a stress run.
Severity: **Major** = wrong behaviour or a defect users meet; **Minor** = cosmetic or edge case.

**Method.** (1) A layout harness loads the real QML with real fonts (Inter, JetBrains Mono), real drives and printers,
sets the window to 2560, 2005, 1600, 1279 and 1024 px, inspector on/off (`Ctrl+I`) and modes A/B (drive and printer
selected), and walks the whole item tree: every visible text item with `truncated == true` or an unplanned line break is
reported, the ribbon spacers and group centre are measured against the middle column, and the Tab chain is recorded
(40 × Tab, 12 × Shift+Tab). (2) Screenshots on the real Plasma desktop with `spectacle` (Vivid Violet Dark, Breeze Dark
and Breeze Light, each with and without KWin blur), the colour scheme restored afterwards. (3) A function test with fake
XDG trees and dummy programs on `PATH` (39 cases, nothing is launched). (4) `pyright`, `qmllint` 6.12.1, and a 60 s
stress run.

### Findings

| # | Area | Severity | Status | Finding and fix |
|---|------|----------|--------|-----------------|
| 1 | qmllint | Major | ✅ | Qt 6.12.1 was installed on the audit day, and its `qmllint` rejects the 2.0.0 file: 11 duplicate ids (`navRoot`, `gaugeFill`, `warnPill`, `pillText`, `pillHover`, `cardMouse` in the drive, network and printer delegates), 44 block-scoped `var`, 3 string literals with real line breaks (`"\n"` in the Python source became a newline in the QML). Ids renamed per delegate, `var` → `let`/`const` (each checked: none is used after its block), the newlines escaped. |
| 2 | qmllint | Major | ✅ | Three untyped lookups: `parent.truncated` on the file-system label of the Properties dialog asked the **GridLayout**, so that tooltip never appeared (real bug); `parent.parent.sel` / `parent.parent.inks` now use ids; `LazyMenu` and `revealItem` cast with `as QQC2.Menu` / `as Flickable`. |
| 3 | Correction | – | ✅ | Earlier entries say "qmllint clean". On the 2.0.0 file, qmllint never ran its *unqualified access* check (blocked by the duplicate ids). Once the errors were gone it reported ~1000 such notes. A nested JavaScript function (first draft of `ribbonStops()`) switches the check off again for the whole file, so that function is written without one. |
| 4 | qmllint | Minor | ⏳ | 1014 *unqualified access* notes remain. They come from the architecture, not from wrong names (all 42 names were checked to be declared): `backend` is a context property (≈320), `win` is used inside inline components (≈260), delegates use the implicit `modelData`/`index` (≈220). The fix is `pragma ComponentBehavior: Bound`, `required property` in every delegate and a typed backend singleton, a larger refactor that was left for later. qmllint exits with 0. |
| 5 | Layout | Major | ✅ | Drive card next to the "⚠ 88 %" pill: "109.9 GB free of …" was cut off in the German UI (113 px of 155 px needed, at every width). Shows "109.9 GB free" (new `freeShort` field) while the pill is visible; full text in the tooltip. |
| 6 | Layout | Minor | ✅ | Compact telemetry at 1024 px was cut inside a number ("▲ 40,…", 237 px of 253 px). The network part is dropped when the full line does not fit (`TextMetrics`, no binding loop). |
| 7 | Layout | Minor | ➖ | Ribbon width: at 2560 px (maximized on the test machine) the four groups are exactly centred (spacers 137/137 px, group centre 1280 = column centre 1280). With both panels the ribbon needs ~2200 px in English and ~2300 px in German; at 2005 and 1600 px it scrolls (291 / 696 px). A compact icon-only ribbon would be the fix (done in 2.1.0: the compact toolbar). |
| 8 | Typography | Minor | ✅ | Tabular figures were missing on five changing numbers: section counters, warning slider %, Properties pie %, ink % in the printer dialog, temperature in the Properties dialog. Everything else (temperatures, I/O, sizes, CPU/RAM, uptime, item count, inspector values) already used JetBrains Mono or `tnum`. Two-line ribbon labels ("Add a network location", "Analyze storage", and their longer German counterparts) wrap by design; no other text is cut off or wrapped at any tested width or mode. |
| 9 | Locale | Minor | ✅ | `sizeShort()` (trash size) used `Qt.locale()`, all other sizes the interface language: "2,9 MB" next to "173.1 GB" when language and number format differ. Unified. Dates still follow the regional format on purpose. |
| 10 | Screen reader | Major | ✅ | Window buttons were named in English on German systems ("Minimize"): `trad()` got a conditional expression, and the translation table only collects literals. Now one `trad("…")` per name; a scan of all `trad(` calls found no other case. |
| 11 | Screen reader | Major | ✅ | No role/name on sidebar rows, the pin button, the "+" button, the sidebar header card and the inspector key/value rows (modes A and B). Added (`Heading`/`ListItem` with size, "not mounted" and `selected`; `Button` with press action; `StaticText` "key: value"). |
| 12 | Keyboard | Major | ✅ | Tab never reached the ribbon or the inspector toggle (`NoFocus`). New chain: main → sidebar → 16 ribbon stops (enabled buttons and *Show* boxes, in visual order) → inspector toggle → minimize, maximize, close → main; Shift+Tab the reverse. Visible focus outline, Enter/Space trigger, hidden buttons scroll into view. Recorded with the harness. |
| 13 | Inspector B | Minor | ✅ | Mounted internal drives had no *Unmount* action (only USB had *Safely remove*). Added with the same rule as the card menu (not for `/`, `/boot`, `/home`, `/var` …). |
| 14 | Printers | Minor | ✅ | Ink warning differed between card/inspector (< 15 %) and dialog (printer threshold). Both rules now apply everywhere; CUPS ink names are translated. |
| 15 | Terminal | Minor | ✅ | Only the user's `kdeglobals` was read; a distribution default in `/etc/xdg/kdeglobals` was ignored. Now a cascade (system first, user overrides). The file manager lookup skips DriveDeck itself. |
| 16 | Tooltip | Minor | ✅ | The inspector toggle tooltip said "(Ctrl+I)" on German systems; now "(Strg+I)", and it also appears on keyboard focus. |
| 17 | Context menus | Blocking | ✅ | **Regression from item 2, reported by the user before any commit:** right-click did nothing anywhere. The cast was written as a statement starting with `(`: `(item as QQC2.Menu).popup()`. JavaScript's automatic semicolon insertion joined it to the line above, giving `item[k] = props[k](item as QQC2.Menu).popup()`, so `popup()` was never called on its own. Now `const menu = item as QQC2.Menu` and `menu.popup()`; a scan found no other line in the QML that starts with `(`, `[` or a backtick. Checked by right-clicking folder, drive, USB drive, printer, sidebar row, sidebar drive and sidebar heading (all menus open, 0 messages); the stress harness now also right-clicks at random positions. The earlier stress run had no right-click, which is why it missed this. |

### Feature checks (no defect found)

- **Default file manager:** `mimeapps.list` chain incl. `kde-mimeapps.list`, uninstalled first choice skipped, localized name, `Exec` field codes (`%U %F %u %f`, `%i` dropped, quoting, `%%`); routing: local folder → default program, `smb://` → Dolphin, missing program → Dolphin → `xdg-open`. Menus show "Open with File Explorer" with its icon.
- **Default terminal:** `xdg-terminal-exec` first, user and system `kdeglobals`, `TerminalService` alone, `$TERMINAL`, configured but missing → fallback, unknown terminal (`-e`), none at all; "Open in Kitty terminal" starts `kitty --directory <dir>` with the folder as `cwd`; a missing folder shows a message and starts nothing.
- **Inspector A:** on this machine "Ryzen 9 5900X · 54 °C", "RTX 4080 SUPER · 52 °C" (nvidia-smi), Kernel, Plasma, `scx_bpfland`, IP · Wayland, uptime, install date, all updating. Missing sensor file → value hidden, no exception; session types Wayland/X11/empty/other.
- **Inspector B:** drive (file system, mount point, device, size, free, used %, temperature, read/write), printer (status, credential-free URI, four ink bars with %), actions as listed; a click in the inspector keeps the selection (unchanged since 5f).
- **Optical drive:** empty drive → grey dot (code path `isOptical && total === 0`); **pins:** pin/unpin from sidebar and cards, saving debounced (unchanged since 5b).
- **Themes:** Breeze Dark and Breeze Light, with and without blur, plus Vivid Violet Dark: cyan version badge, specular hover, hairlines and sub-labels readable in all of them; only disabled items (*Properties*/*Open* without selection, unmounted drives) are intentionally faint.

**Checks:** `pyright` 0 errors; `qmllint` 6.12.1 exit 0 with 0 errors and 0 warnings outside the *unqualified* category (item 4);
function test 39/39; layout harness without unexpected truncation at 2560/2005/1600/1279/1024 px; 60 s stress run
(about 5400 random actions on the final code: drive/printer list changes, minimise, resize between 1024 and 2560 px, `Ctrl+I`, mode A/B switches,
Tab/Shift+Tab/Space, arrow keys, temperatures) with **0 QML messages** (no binding loop, no `ReferenceError`), 0 exceptions,
RSS between 185 and 199 MB without a trend (an earlier run of the same harness: 5566 actions, 0 messages). One stress run ended early because a random Tab reached *Close* and Space
pressed it. That is correct behaviour; the harness now skips Space on window buttons.

---

**Release 2.0.1 check:** the "Open" entry of folder cards and sidebar rows now uses the same file-manager label as drive and
network cards (`openLabel()`/`openIcon()`: local paths → "Open with File Explorer", `smb://` and other addresses → "Open",
because they open through Dolphin/KIO). `pyright` 0 errors, `qmllint` 0 errors and 0 warnings outside *unqualified*
(1022 notes: the new helper reads `backend`, same category as item 4), right-click test on folder, drive, USB drive, printer
and sidebar rows (all menus open, 0 messages). The user confirmed on the real desktop that right-click opens at the pointer
and that File Explorer and Kitty start.

---

## 5m. Upstream cherry-picks (2.1.0)

Five non-destructive ideas from the comparison with Fenestra This PC 2.1.1 (code was not copied; each is written for
DriveDeck's architecture). Formatting, the surface scan and the 3-second disk refresh in the GUI thread were deliberately
not taken over.

| # | Area | Status | What was done and how it was checked |
|---|------|--------|---------------------------------------|
| 1 | Scanners | ✅ | `scanner_ip()` reads the address from `ip=`, `http(s)://` (IPv4 and IPv6) and `:net:`; `scanner_modellkern()` drops the source list and "Series"; `scanner_zusammenfassen()` groups by address **or** model and keeps the entry with a source list / eSCL address. Applied after each search, to the merged known list and to the cache on start. Real case on the test machine: `escl:https://<IP>` + `airscan:e0:…` → one card "Epson WF-4830 (Flachbett & ADF)". Unit test with three drivers for one Epson, an HP via `hpaio …?ip=`, and a USB scanner → three cards. |
| 2 | SMART | ✅ | `smart_udisks()` (busctl, no root): NVMe `SmartGetAttributes` + controller properties, ATA attributes 5/12/197/198/231–233/202 + `SmartFailing`, `SmartPowerOnSeconds`; Kelvin → °C; Good/Warning/Critical with reasons; 60 s cache per drive, plus a 60 s throttle per device in `requestSmart()`; read in a thread, result handed to the GUI thread by a queued signal. Real data: both NVMe drives (3 % / 0 % wear, 14 482 h / 14 880 h, 52.7 / 29.5 TB written, 46 / 39 °C, "Good"); USB SSD → `None` (no `Drive.Ata`), so the card says so and the `smartctl` report stays the way. ATA path checked with mocked udisks2 data (8 reallocated sectors → "Warning"). Shown in inspector mode B (collapsible, keyboard/screen-reader button) and the Properties window. |
| 3 | Toolbar | ✅ | Automatic 48 px compact toolbar. Measured offscreen with both panels: full ribbon at 2560/2400/2300 px (need 1610 px, available 1874/1714/1614 px), compact at 2005/1600/1279/1024 px, compact row centred in the middle column (≤ 0.5 px off), back to full when widened. First draft used a `Binding` whose `when` depended on the result → "Binding loop" (caught by the test); replaced by `Qt.callLater` hand-over, 0 messages since. Tab chain in compact mode: sidebar → 10 enabled buttons + "…" → inspector toggle → window buttons → main. Found on the way: the ribbon scroll bar stayed visible above the compact toolbar because attaching it to the Flickable overrides its `visible`; it now lives in a wrapper item. |
| 4a | Printers | ✅ | Debounce with `DRUCKER_MAX_FEHLER = 3` under a lock (one probe thread per printer). Unit test with the sequence reachable/–/–/reachable/–/–/–/–: offline only on the 3rd failure in a row, counter reset by a success, ink levels kept during the drop-out. |
| 4b | Click mode | ✅ | `QFileSystemWatcher` on `~/.config` and `kdeglobals`, 300 ms single-shot timer, read only on a changed mtime, file re-added after replacement. Test: replace (as KConfig does) true/false/true and an in-place edit → singleClick follows each within 800 ms. In the stress run the mode switched both ways. Limitation: a `~/.config` that does not exist at start is not watched (never the case in a real session). |
| 4c | Inks | ✅ | `tinte_name()` by partial match (photo/matte black, light cyan/magenta/gray, black, cyan, magenta, yellow, gray; "toner" kept as suffix); `TINTE_SCHWELLE = 10` when `marker-low-levels` is missing or ≤ 0. QML (pills, pulse, tooltip, inspector, dialog) now reads only `low`, so there is one rule instead of the former fixed 15 % in the card. |

**Checks:** `pyright` 0 errors; `qmllint` exit 0, 0 errors, 0 warnings outside *unqualified* (1117 notes, the same
architectural category as 5l item 4; the new toolbar and SMART code read `backend` and `win` like the rest); function test
39/39; right-click test (cards and sidebar) 0 messages; offscreen layout test above 0 messages; 60 s stress run on the final
code (about 5300 random actions incl. resizes between 1024 and 2560 px through the compact/full switch, Ctrl+I, mode A/B
switches that request SMART, right-clicks on cards and the toolbar, replacing `kdeglobals`) with **0 QML messages**,
0 exceptions, RSS 179–203 MB without a trend, click mode seen as both single and double. Translations: all new texts
have German entries (a scan of all `trad("…")` literals leaves only words that are the same in German).

**Not verified:** a real SATA disk through udisks2 (none in the test machine), the compact toolbar on the real desktop
(only offscreen screenshots), and Orca reading the new sections.

---

## 5n. SMART for NVMe drives in USB enclosures (2.1.0)

**Report (user):** Properties → SMART status of a FIKWOT FN501Pro 1 TB in a USB enclosure showed only "SMART support is:
Unavailable - device lacks SMART capability."

**Cause:** for USB disks the cascade started with `-d sat`. A USB-to-NVMe bridge answers ATA pass-through with an identity
placeholder and no SMART data. `smart_ok()` only rejected a fixed list of error texts, and "Unavailable" / "lacks SMART
capability" / "Unknown" were not in it, so the placeholder ended the cascade as if it were a result.

**Measured on the device** (root via pkexec, read-only `smartctl -a`; the password was entered by the user):

| Call | Result |
|------|--------|
| `smartctl -a` (no `-d`) | full NVMe health log, rc 0 (smartmontools 7.5 knows `0bda:9210` in its USB database) |
| `-d sat -T permissive` | "SMART support is: Unknown … A mandatory SMART command failed", rc 4 |
| `-d sntrealtek` | full NVMe health log, rc 0 |

Bridge from sysfs: USB `0bda:9210` "RTL9210 M.2 NVME Adapter". The device reports 25 media and data integrity errors,
which the new SMART section shows as a warning.

**Fix:** `usb_bridge_hersteller()` reads the USB vendor ID from sysfs; `smart_varianten(usb, base)` tries the matching
`snt*` driver first, then no `-d`, `-d sat`, the other `snt*` drivers and `-d nvme`; `_SMART_FEHLER` rejects the
placeholder texts; smartctl runs with `LC_ALL=C`. `smartctl_werte()` turns a report (NVMe health log or ATA attribute
table) into the same values as `smart_udisks()`; `_smartWerteMelden()` caches report and values for 60 s and hands the
values to the inspector and the Properties window. New slot `readSmartUsb()` and an inspector button for drives without
udisks2 SMART data. A cancelled password prompt (pkexec 126/127) no longer opens a message.

**Checks:**
- Real device through DriveDeck's own root path (same `pkexec sh -c SMART_ROOT_SKRIPT` call, new order): first driver
  `-d sntrealtek` answered, no placeholder in the report, parsed: 0 % wear, spare 100 % (limit 1 %), 1781 h, 5621 power
  cycles, 88 unsafe shutdowns, 3.89 TB written (shown as 3.54 TB because DriveDeck uses binary units everywhere),
  25 media errors → "Warning". The parser also reads the locale-formatted numbers of the first probe ("1.781").
- Unit tests: placeholder and "Unknown" answers rejected, a good report accepted; ATA attribute table parsed (hours
  21 345, cycles 1204, 2 pending sectors → warning); the last self-test "Completed without error" is a success. A first
  draft matched "error" inside "without error" and called it a failed test; caught by this test and fixed. Second
  `_smart()` call within 60 s: 0 further pkexec calls, values delivered from the cache.
- Offscreen screenshot of the inspector card for the USB disk: before reading (hint + **Read SMART…**) and after (values,
  "Read with smartctl at 22:31", warning pill), 0 QML messages.
- `pyright` 0 errors; `qmllint` exit 0, 0 errors, 0 warnings outside *unqualified* (1118); function test 39/39;
  60 s stress run on this code (about 5400 random actions incl. selecting the USB disk, which requests udisks2 SMART and
  falls back to the cached smartctl values, never to pkexec) with 0 QML messages, 0 exceptions, RSS 188–204 MB.

**Not verified:** JMicron and ASMedia bridges (only the Realtek path exists on the test machine); SATA disks in a USB
enclosure on real hardware.

---

## 5o. Finder-style side columns (2.2.0)

**Request:** sidebar and inspector should look like macOS Finder / System Settings: no box-in-box, one luminance step and
one 1 px hairline per column, calm rows and icons, a Finder "Get Info" grid in the inspector. Icons keep their theme
colours (the user chose against tinting them).

**Findings on the user's screenshot** (it showed a 2.0.0 window that was still running; the installed copy was 2.1.0, the
side columns look the same in both): three frame levels (window → floating panel with outline and light edge → cards with
outline and light edge); panels starting 8 px below the window edge while title and ribbon touch it; a 330 px sidebar with
22 px coloured icons next to 16 px headings and row heights of 32 and 46 px; labels and values at opposite edges of the
inspector; bordered selection pills and upper-case headings.

| Area | Change |
|------|--------|
| Material | `SideMaterial`: full height, fill `rgba(255,255,255,0.03)` / `rgba(0,0,0,0.025)`, outer corners follow the window radius (clipped rectangle), one 1 px hairline (8 %) towards the middle. Floating panels, outlines, `SpecEdge` light edges and the cursor spotlight removed. |
| Sidebar | 230 px; rows 32 px; pills 10 px margin, radius 7, selection 18 % / 10 %, hover 7 %, 150 ms `ColorAnimation`; icons 16 × 16, 10 px to text; headings 11 px DemiBold 50 % in sentence case, chevron on hover; drives: 2 px capacity line + size (11 px, tabular), eject/pin replace it on hover; tree indent 14 px per level, guide lines removed; plain header row above a hairline. |
| Inspector | 300 px (280 px cut off "192.168.178.49 · Wayland" and German labels); 16 px margins, hairlines between sections, no cards; header icon 44 px, title 15 px DemiBold, subtitle 12 px 60 %; `KvRow`: label right-aligned in a fixed 40 % column (12 px, 60 %, wraps to two lines), value left-aligned (12 px, tabular figures, middle elision with tooltip); `LiveRow` with 24 px sparklines under "Activity"; SMART chevron before the title; `StatusBadge` (radius 5, 18 px, 16 % fill, no outline) with Apple system colours, also for the update status. |

**Found and fixed during the work:** "Unable to assign [undefined] to bool" for tree rows without an `expandable` field
(now compared with `=== true`); the German label for "Local Disk" 6 px short in the sidebar (right margin 12 px, 6 px gap to the size).

**Checks:** `pyright` 0 errors; `qmllint` exit 0, 0 errors, 0 warnings outside *unqualified* (1107, fewer than before);
truncation scan of both columns in modes A and B (root disk, USB disk, printer) at 2560 px: only the long printer URI is
elided in the middle on purpose; real-desktop screenshots in Vivid Violet Dark and Breeze Light with blur (scheme restored
afterwards); right-click test 0 messages; layout test: compact toolbar now below about 2175 px with both columns; function
test 39/39; 60 s stress run (about 5500 actions) 0 QML messages, 0 exceptions, RSS 185–203 MB, click mode seen both ways.

**Not verified:** Orca reading the regrouped inspector; very large system fonts (sizes use `fontGrow`, only the default
size was looked at).

## 5p. Visual design audit against the Apple HIG (2.2.0)

**Request:** a strict visual audit along the Apple Human Interface Guidelines (macOS, Liquid Glass): 4/8 px grid, optical
alignment, concentric radii, layer depth and alpha values in dark and light, typography and WCAG AA, tabular figures,
icon weight, status colours, whitespace, and interaction/focus states; findings first, changes after approval.

**Method:** the QML was scanned for every margin, padding, spacing and radius off the 4 px grid; the window was rendered
offscreen at 2400 × 1300 in Breeze Light, Breeze Dark and Vivid Violet Dark, with nothing selected and with a drive
selected. For every visible text the background was taken from the rendered pixels under it, the text colour was blended with
its effective opacity, and the WCAG contrast ratio was computed (`vis.py`).

| Finding (before) | Measured | Fix |
|---|---|---|
| Secondary text dimmed by `opacity` 0.5–0.6 | Breeze Light 3.05–4.08, Vivid 3.86–4.36 | `textSecondary` 70 / 72 %, `textTertiary` 62 / 66 % as colours |
| Unmounted drives: whole row at 48 % | 2.89 (Light), 3.65 (Vivid) | label `textSecondary`, only the icon at 50 % |
| Two status palettes (theme negative/neutral, Material blue, Tailwind cyan/magenta next to Apple colours) | "⚠ 88 %" 3.46–3.67, ▲ 2.59, "Good" 3.57 (Light) | one Apple palette; badge text `Qt.darker(tone, 1.25)` in light themes |
| Neon gradient (`CardGlow`) and cyan version badge | – | neutral surface + hairline; neutral capsule |
| Three selection languages, a 3 px accent stripe | – | hover 7 % neutral, selection accent 18 / 10 %, no stripe |
| Toolbar hovers toggled via `visible`; 120/140/150/250/300 ms, linear/InOutQuad | – | 150 ms OutCubic everywhere; 3 px focus ring outside (`FocusRing`) |
| Radii 1.5, 2, 3, 4, 5, 6, 7, 8, 10, 12 | – | 4 / 6 / 8 / 12; panel 12 = tile 8 + 4 |
| Sidebar rhythm 33 px, headings at x 18 vs. 16, margins 14 / 16, width 230 | – | 32 px rhythm, one 16 px edge, 240 px |
| Section titles: capitals, accent pill with border, rule | count 3.24 (Light) | sentence case 13 px DemiBold, plain count, 24 px above |
| Pure RGB ink colours from the printer | yellow ≈ 1.1 : 1 on white | snapped to print tones, inner hairline in light themes |
| Off-grid values 1, 3, 5, 6, 7, 9, 10, 14, 17, 18, 26, 67 | – | moved to the 4 px grid (the 17 px inspector margin stays: 16 px + hairline) |

Tabular figures were already set on every live value (sizes, rates, temperatures, SMART values, counts); nothing was missing.

**Checks:** `pyright` 0 errors; `qmllint` (Qt 6.12) exit 0, 0 errors, 0 warnings outside *unqualified* (1147); contrast
scan after the change: 0 failing labels in all three schemes with a drive selected, and only the disabled toolbar buttons
(WCAG exempt) with nothing selected; compact-toolbar threshold unchanged at about 2175 px; Tab chain unchanged; right-click
test 0 messages; function test 39/39; 60 s stress run (about 4800 actions) 0 QML messages, 0 exceptions, RSS 171–201 MB,
click mode seen both ways; real-desktop screenshots with blur in Vivid Violet Dark and Breeze Light (scheme restored
afterwards).

**Not verified:** contrast over very bright wallpapers behind the 93 % glass in dark themes (measured without blur);
Orca; very large system fonts.

## 5q. Network limitations, settings dialog, notifications (2.3.0)

**Request:** fix the three known limitations (IP vs. host name, disconnect without an `fstab` entry, KWallet removal),
bring all app settings into one dialog (`Ctrl+,`, gear button, "…" of the compact toolbar) and add optional desktop
notifications; keep the single file, keyboard navigation, screen-reader names and 0 findings in `pyright` / `qmllint`.

| Area | Implementation | Check |
|---|---|---|
| IP ↔ host name | `gleiche_freigabe()`: same share (case-insensitive) and same host as text, otherwise intersecting `host_adressen()` sets; `getaddrinfo` in a helper thread, at most 1 s, cached 5 min (1 min after a failure), no second lookup while one is still running, IPv6 zone ids stripped; only called from the network thread, and only when the share matches but the host text does not | 12 unit checks with a fake resolver, including a resolver that hangs (returns after 0.3 s) |
| Disconnect without rights | `umount_braucht_root()` recognises "must be superuser", "only root", "operation not permitted", "permission denied"; the backend emits `unmountAdminOffered`, QML asks once, `unmountNetworkAdmin()` runs `pkexec umount` only for a mount point that is currently a network file system; 126/127 (cancelled) stay silent | unit checks; offscreen: prompt appears and no `pkexec` runs before the confirmation |
| KWallet | `wallet_entfernen()`: `open` / `removeEntry` / `close` on `org.kde.KWallet` through `busctl --user` (kwalletd6, then kwalletd5); `wallet_loeschen()` falls back to blanking | unit checks of the call sequence and fallbacks; on the real desktop a probe entry in DriveDeck's own folder was written, removed and confirmed gone with `hasEntry` |
| Notifications | `notifications` in `settings.json` (default off); `_warnungenPruefen()` runs on every disk and network update and once when switched on; one message per (reason, device) and session; `desktop_benachrichtigung()` tries `notify-send`, then `Notify` over D-Bus | unit checks of the fallback; a real test notification arrived on the desktop |
| Settings dialog | gear `ToolButton` (28 px × `fontGrow`, tooltip, `Accessible.name`, focus ring) in the window's Tab chain right before the inspector toggle; `Ctrl+,`; "…" menu and toolbar context menu; dialog with its own header (title aligned with the 20 px content edge), opaque surface (it was 97 % first – card text showed through, and there is no blur behind a popup), hairlines between the groups | offscreen (Breeze Dark and Light): `Ctrl+,` and the gear open it, the name field has focus, Tab cycles through all eleven controls with names, test notification, switch and slider (keyboard) are saved, the name is applied, `Esc` closes, **Warning threshold…** focuses the slider; real-desktop screenshot in Vivid Violet Dark |

**Checks:** `pyright` 0 errors; `qmllint` exit 0, 0 warnings outside *unqualified* (1131, 16 fewer than before because
the threshold popup is gone); translation check: 334 strings used, none missing or unused in any of the 12 `.po` files,
placeholders consistent, `msgfmt --check-format` clean; 23 unit checks and 20 offscreen checks passed, 0 QML messages
from DriveDeck; 60 s stress run (about 5000 actions: `Ctrl+,`, Tab and arrow keys, `Esc`, window widths 1024–2560,
inspector on/off, notifications on/off) with 0 QML messages, RSS 216–220 MB and exactly one notification for the one
drive above the threshold.

**Not verified:** a real `pkexec umount` of a share mounted through `/etc/fstab` without `user` (no such share on the test
machine); a host name that resolves to several addresses on different networks; notifications on desktops other than
Plasma.

## 5r. Header hairline alignment (2.3.1)

**Report (two screenshots):** the hairline under the sidebar header and the one under the inspector header were at
different heights; with the compact toolbar a third height appeared under the toolbar.

**Measured before (offscreen, font scale 1.09):** sidebar line y = 68, inspector line y = 100, line under the toolbar
y = 99 (compact) or 180 (ribbon); the side lines were inset by 16 px.

**Fix:** one header height `topBarH` = round(88 × fontGrow) for both side columns, split into `titleBarH` =
`topBarH` − `compactBarH` (title bar of the middle column) and a band of `compactBarH`. The middle title bar uses
`titleBarH`, so title bar + compact toolbar end exactly at `topBarH`. Side headers centre their content in the lower band,
the inspector's window buttons in the upper band; all three lines are at `topBarH` − 1 and run the full column width
(1 px short of the vertical column lines so the junction is not drawn twice). A requested height of 68–72 px was not
possible: the compact toolbar alone is 48 px and the title band needs room for the 28 px settings button.

**Check after:** y of the three lines at 2560 px (ribbon), 1900 and 1500 px (compact automatically) and 2560 px
(compact forced), nothing selected and a drive selected: **0 px difference** in every case; in compact mode the middle line
spans exactly from the sidebar's column line to the inspector's. `pyright` 0 errors, `qmllint` 0 warnings outside
*unqualified* (1134); settings-dialog test 20/20; 60 s stress run 0 QML messages, RSS 223 MB; real-desktop screenshots of
both modes in Vivid Violet Dark.

## 5s. Glass dividers and a larger sidebar (2.3.1)

**Request:** dividers 1.5–2 px with a translucent glass tint (dark `rgba(0.80, 0.86, 0.96, 0.12)`, light
`rgba(0.10, 0.14, 0.22, 0.11)`) without losing the header alignment; sidebar entries 13 px with 18 px icons and 32–34 px
rows, headings 11.5 px semi-bold, about 240 px wide, no truncation.

**Implementation:** tokens `hairline` (the new tint, used by every divider), `dividerW` = 2 (column dividers in
`SideMaterial`, the three header lines, the line under the ribbon/compact toolbar) and `sectionLineW` = 1.5 (`Hairline`,
ribbon group separators, `CompactSep`). Header lines now cover `topBarH − dividerW … topBarH`; horizontal lines stop
`dividerW` short of the vertical dividers, and the inspector content starts `16 + dividerW` from its divider. Sidebar rows
34 px × font scale, icons 18 px, labels `px13`, headings 11.5 px via point size (pixel sizes are whole numbers only). The
first measurement cut "Lokaler Datenträger" by 3 px in German, so the sidebar went from 240 to 248 px.

**Checks:** line positions at 2560 px (ribbon), 1900 px and 2560 px (compact): top and bottom of all three header lines
identical (0 px), 2 px thick, ending at `topBarH`; in compact mode the middle line spans exactly between the two
vertical dividers. No sidebar text cut off in German, English, Russian, French, Dutch and Polish. The ribbon needs 3 px
more for the wider group separators (1681 → 1684 px in German at font scale 1.09), so the compact toolbar still takes over
well above 2000 px. `pyright` 0 errors, `qmllint` 0 warnings outside *unqualified* (1145); settings-dialog test 20/20;
60 s stress run 0 QML messages, RSS 224 MB; screenshots in Breeze Dark and Light.

**Noticed, not changed:** at font scale 1.09 (offscreen) the German drive card cuts "Lokaler Datenträger" and its
free-space text by a few pixels, exactly as before this change: the cards are a fixed 340 px wide and do not grow with
the font.

## 5t. Section headers of the main area (2.3.1)

**Request:** category-style headers (12 px semi-bold capitals, 0.8 tracking, muted white/black), a rotating 12 px chevron,
the count in an accent glass capsule with a soft glow, a fading 1.5 px glass rule, a hover surface and full keyboard
support.

**Implementation:** component `SectionHeader` (replaces `SectionTitle` and the arrow-only `MouseArea`); the button part
(chevron, title, capsule) has `Accessible.role: Button`, `Accessible.name` "title, count", a `FocusRing`, `HoverHandler`
and `TapHandler`; the glow is a hidden accent rectangle blurred by `MultiEffect` (opacity 0.20, 0.34 on hover/focus),
hidden when `GraphicsInfo.api` is software. Tab chain: `enterSections()` / `sectionMove()` between the main area and the
sidebar; Backtab from the sidebar (or from the first ribbon stop without a sidebar) returns to the last header.

**Found during the check:** with `Qt.lighter(accent, 1.45)` / `Qt.darker(accent, 1.45)` the count reached only 4.06 : 1
in a dark violet scheme and 3.95 : 1 in Breeze Light (`Qt.lighter` barely lifts a dark, saturated violet). It is now
`Qt.tint(accent, white 60 % / black 50 %)`: titles and counts measured 6.0–9.9 : 1 in Breeze Dark, Breeze Light and
Vivid Violet Dark, including the hovered header.

**Checks:** header test 14/14 in all three schemes (four headers with names, Tab main → four headers → sidebar, Space
and Enter fold, a click on the title folds, Esc returns to the main area); `pyright` 0 errors, `qmllint` 0 warnings outside
*unqualified* (1157); settings-dialog test 20/20; header lines still 0 px apart; 60 s stress run 0 QML messages, RSS
225 MB. The glow and the chevron rotation were looked at on the real desktop by the user.

## 5u. System information as a hardware inspector (2.4.0)

**Request:** a freely resizable window with a remembered size and a two-column layout from 960 px, the main window's
style, a *Sensors & fans* and a *Storage & buses* category, the socket without root, `Ctrl+F` search with hit counts,
click to copy, and every label translated.

**Implementation:** `QQC2.ApplicationWindow` `hwWin` (min. 820 × 580, start 1180 × 780) replaces the modal dialog;
`openHardware()` restores size and maximized state from `backend.hwWindow`, `saveHwWindow()` stores the last windowed size
on close. Cards are distributed greedily into the shorter column. `hwmon_lesen()` / `_sensorGruppen()` (min/max per sensor
and session) run in a thread that `setSensorsActive()` starts when the window becomes visible and stops when it hides.
`sammle_busse()` (PCI classes via `lspci -vmmk`, `/sys/bus/pci/devices/*/nvme`, `/sys/class/ata_link`,
`/sys/bus/usb/devices`) and `sockel_ableiten()`. `_gruppe()` now translates titles and keys and keeps `en` / `ven` for
the English export.

**Found during the work:**
- **qmllint analysed only part of the file.** With the new window the *unqualified* count dropped from 1157 to 325 while
  the exit code stayed 0: the warnings ended at line 2435, just before the window. Removing pieces showed that JavaScript
  callbacks (`map`, `filter`, `reduce`, `find` with a function) stop the analysis for the rest of the file. The window
  now uses plain loops; the whole file is analysed again (1184 *unqualified*, last at line 6256 of 6319), which also
  surfaced 12 real `missing-property` findings (`contentY` on `ScrollView.contentItem`) that are fixed with `as Flickable`.
- **Row index past the end:** the window stress run showed "Cannot read property 'k' of undefined" when a search
  shortened the list while a row was chosen; the choice is now clamped and copying checks its argument.
- `raise()` is not supported on Wayland and only printed a warning; `requestActivate()` is enough.
- Unconnected mainboard probes reported −1 °C; temperatures outside 0–127 °C and fan headers that never turned are hidden.
- The chipset "B650M" (form factor suffix) was not recognised for the socket.

**Checks:** window test 21/21 in Breeze Dark, Breeze Light and Vivid Violet Dark (opens at 1180 × 780 with min. 820 × 580,
one column at 900 px, two at 1500 px, arrow keys in the categories, Tab into the content, Enter copies, `Ctrl+F` focuses
the search, "nvme" finds the two NVMe controllers and shows hit counts, `Esc` clears and then closes, a click copies,
sensors with min/max, the size is saved); without sensors 20/20 with the explanation; window stress run 40 s (2236
actions, 113 re-openings, resizing, searching, switching) 0 QML messages, RSS 211 MB, sensor thread stopped after close;
real data: two NVMe drives at PCIe 4.0 x4, eleven USB devices from 12 Mb/s to 10 Gb/s, "AM4 (derived from the X570
chipset)", k10temp, NVMe, DIMM, nct6797, NZXT X53 and the RTX 4080; translation check: all 12 `.po` files complete
(445 entries); `pyright` 0 errors; settings, header and line tests unchanged; 60 s main-window stress run 0 QML messages.

**Not verified:** the window on the real desktop (the user looks at it before committing); AMD/Intel GPUs in the sensor
list; USB4/Thunderbolt speeds; at 1180 px with a larger font scale the content is below 960 px and stays one column.

## 5v. Card rows, merged cards and the Network tab (2.4.0)

**Request:** logical pairs of equal height instead of shortest-column masonry, full-width cards for lists and tables,
merged memory sensors and controllers, calm card titles, the remaining English values translated, and a Network tab with
the active connection, its adapter and data usage (session, today, week, month; `vnstat` plus an own counter that
survives reboots).

**Implementation:** `zeilen()` builds rows of two cards in report order (a `wide` card or one left over gets a row of its
own); every row is a `RowLayout` whose cards use `Layout.fillHeight`, so both cards take the taller height. `_gruppe()`
learned `breit` (full width), `spalten` (table header, rows as cell lists) and value pairs (translated, English) through
`_zw()` / `_verbinde()`. `netz_live()` builds the Network tab every 2 s while the window is open; `NetzZaehler` keeps the
daily totals in `net_usage.json` (background sample every 60 s, saved at most every 5 minutes and in `shutdown()`).

**Checks:** card rows measured in every tab in Breeze Dark and Light: top and height of the two cards of a row differ by
**0 px** (overview 3 pairs; CPU 2 pairs + 1; GPU 1 + 1; memory 1; storage 2 + 1; sensors 3 + 1; system 1 + 4; network 1 + 2);
counter unit tests 10/10 (first run, growth, reset without reboot, reboot via `boot_id`, reload without double counting,
today/week/month boundaries, broken file); window test 21/21 (20/20 without sensors); window stress run 40 s (2203
actions, 111 re-openings) and main-window stress run 60 s with 0 QML messages; settings, header and line tests unchanged;
`pyright` 0 errors, `qmllint` 0 warnings outside *unqualified* (1196, analysed to line 6298 of 6363); all 12 `.po` files
complete (480 entries). Real data: enp38s0 at 1000 Mb/s full duplex, IPv4/IPv6, gateway and DNS behind systemd-resolved,
Intel I211 at PCIe 1.0 x1, data usage table with live rate.

**vnstat (installed afterwards, 2.14):** the service runs, but a fresh database has no day entries yet – the parser then
returns nothing and the own counter stays in use. Using vnstat as soon as it had a few minutes of data would have shown
only those minutes for today, the week and the month, so the source is now chosen **per period**: vnstat only when its
database was created before the period began. Tested with the real (empty) output and simulated output: created today →
own counter; created 60 days ago → vnstat for all periods; created yesterday → vnstat for today, own counter for week and
month, and the source line names both ("vnstat since … · counted by DriveDeck since …"); 7/7.

**Not verified:** vnstat with real day entries (the database was minutes old); the first day after installing DriveDeck
counts all traffic since the last boot as "today"; Wi-Fi without a link speed in sysfs.

## 5w. Sensor card grouping and fan control (2.4.0 draft; the write part was removed again in 5x)

**Request:** sensor cards of similar size side by side (CPU + GPU, memory + liquid cooler, drives in pairs), the mainboard
card over the full width with temperatures and fans in two columns, the fan control state (BIOS vs. `fancontrol`) and
optional PWM presets through `pkexec` with a 30 % floor in manual mode.

**Implementation:** `_sensorGruppen()` sorts temperatures before fans (`col` 0/1), marks a card with more than six
readings `wide` and, when it has both kinds, `split`; narrow cards keep the CPU → GPU → memory → cooler → drives order and
wide cards are placed after the first two pairs. In QML the rows of a card sit in a `GridLayout` (one column, or two with
explicit `Layout.row`/`Layout.column` when split and the window shows two columns); the fan control row (`col` 2) spans
both columns, and its key column matches the left column so the values line up. `luefter_regelung()` reads
`pwmN_enable`/`pwmN` and the fancontrol state; `pwm_auftraege()` builds `N:enable:pwm` jobs (and saves the automatic
state before the first manual preset), `pwm_schreiben()` writes directly when the files are writable, otherwise runs
`PWM_ROOT_SKRIPT` once through `pkexec` in a thread (`fanBusy` disables the buttons meanwhile; 126/127 = cancelled,
silent; other exit codes are reported). The hardware window's repeaters now take counts as models and read their data by
index: before, every 2 s sensor update replaced the whole JavaScript array and rebuilt every card – a preset button
would have been destroyed between press and release, and hover and tooltips flickered.

**Safety:** the root helper validates everything itself (path `/sys/class/hwmon/hwmon` + digits only, so no `..`;
exactly three numeric fields; mode ≤ 5; duty ≤ 255; channel must exist) and raises manual duty below 77 to 77. Only
chips classified as *Mainboard* get the row; liquid coolers (e.g. the X53 here) and GPUs are never written. Presets
are disabled while `fancontrol` runs. *BIOS auto* without a saved state does not guess a mode but explains that the
BIOS restores it at the next restart. A pump on a mainboard header slows down with the other headers – the tooltip
says so.

**Checks:** unit tests on a fake hwmon tree 26/26 (channel detection, BIOS/manual/mixed/daemon states, preset
recognition, snapshot written once and kept, restore jobs, missing snapshot, direct write with floor, and the real root
script: quiet preset, 30 % clamp, rejected `..` path, foreign directory, duty > 255, mode > 5, injected characters, two
or four fields, missing channel). Window test of the sensors tab 14/14 in Breeze Dark, Breeze Light and German: rows
*CPU + GPU*, *Memory + Liquid cooler*, *Mainboard* (6 temperatures | 4 fans, columns 589/590 px), *NVMe + NVMe*;
pairs 0 px apart; fan control row last and full width; four presets with *BIOS auto* checked; a click on *Quiet* calls
the writer with `1:1:115` for hwmon5 and saves the snapshot but does not copy the row; a click on the row still copies;
buttons and rows survive a sensor update. Narrow window (one column) 8/8. All tabs still 0 px; window test 21/21
(20/20 without sensors); window stress run without leaks, sensor thread stops after closing. `pyright` 0 errors,
`qmllint` 0 warnings outside *unqualified* (1222, analysed to line 6383 of 6448); 14 new texts in all 12 `.po` files
(495 entries).

**Not verified:** a real `pkexec` write to the nct6797 (it needs the user's password; the helper was run against a fake
tree, and the real PWM state – all seven channels in mode 5 – was only read); how the presets look in the real Breeze
style (offscreen draws no button icons, so the check mark of the active preset was confirmed as a property only).

## 5x. Fan control back to read-only (2.4.0)

**Request:** keep the hardware inspector a clean, read-only monitor without root changes: remove the four presets, the
`pkexec` root helper, the PWM write functions and the `fan_bios.json` logic; keep the two-column mainboard card and the
plain *Fan control* info row; remove the texts that are no longer needed.

**Removed:** `FAN_BIOS`, `PWM_MIN`, `FAN_PRESETS`, `PWM_ROOT_SKRIPT`, `_fan_kennung()`, `fan_bios_lesen()`,
`fan_bios_speichern()`, `pwm_auftraege()`, `pwm_schreiben()`; in the backend `fanBusy`/`fanBusyChanged`, `_fanFertig`,
`setFanPreset()` and `_fanErgebnis()`; in QML `hwWin.fanPresets`, the `hwFanWahl` flow with its buttons and `hwFanHover`
(the row tooltip shows on hover again without the exception). The sensor items no longer carry a `fanctl` object.
8 texts left all 12 `.po` files ("BIOS auto", "Quiet {p}", "Performance {p}", "Max {p}", the two button tooltips and the
two error messages), now 487 entries each; `.mo` recompiled.

**Kept:** `pwm_kanaele()` and `fancontrol_aktiv()` (only read `pwmN_enable`, `pwmN` and `systemctl is-active`), and
`luefter_regelung()`, which now returns only `{v, ven}`: "fancontrol active", "BIOS automatic", or "Manual · N %" when
another tool (pwmconfig, a vendor tool) has set the outputs to manual – showing "BIOS automatic" there would be wrong.
The split card (temperatures | fans) and the full-width info row are unchanged; the count-model repeaters from 5w stay.

**Not removed:** an existing `~/.local/share/drivedeck/fan_bios.json` from testing the draft is no longer read or
written; it is left in place (DriveDeck deletes no user files on its own) and can simply be deleted. Note: `uninstall.sh --purge` does not remove it either – it only clears `~/.config/drivedeck` and the caches; `net_usage.json` in the same folder stays as well.
The real PWM state here is again all seven channels in mode 5 (SmartFan IV).

**Checks:** unit tests on a fake hwmon tree 9/9 (channel detection; BIOS, manual-set-elsewhere and fancontrol states;
five calls leave every file byte- and mtime-identical; no `fan_bios.json` is created; a chip without PWM gives no row;
none of the removed module or backend symbols exist). Window test of the sensors tab 12/12 in Breeze Dark, Breeze
Light and German: rows *CPU + GPU*, *Memory + Liquid cooler*, *Mainboard* (6 temperatures | 4 fans), *NVMe + NVMe*,
pairs 0 px apart, two equal columns, the info row last and full width with "BIOS automatic" / "BIOS-Automatik", no
preset buttons, no write slot, rows survive a sensor update, a click on the row copies it; narrow window (one column)
4/4. Window test 21/21 in Breeze Dark and Light; window stress run without leaks, sensor thread stops after closing.
`pyright` 0 errors, `qmllint` 0 warnings outside *unqualified* (1215, analysed to line 6356 of 6421).

**Not verified:** the card on the real desktop with the real Breeze style.

## 5y. Glanceable hardware window (after 2.4.0)

**Request:** a "glanceable and data-driven" refresh of the system data window across all hardware tabs: a hero header
(product name 16 px bold, glass badge), 3–4 KPI tiles (14 px semi-bold value, 11 px label), secondary details in two
columns, shortened technical strings with the full value in the tooltip and when copying, display tiles, and version
pills for the graphics APIs; click-to-copy, keyboard navigation, `Ctrl+F` and the 1.5 px glass lines kept. Three previews
were rendered with the real hardware data (A data sheet, B tiles, C instrument); the user chose **B**.

**Data model:** `_gruppe()` takes `hero`, `badges`, `icon` and `akzent`, and every value may carry its presentation:
`role` (`hero`, `sub`, `kpi`, `mon`, or none for a row), `d` (short display text), `tl` (tile label), `ts` (tile subline),
`mon` (display data). `v`/`ven` always keep the full value, so search, click-to-copy and the exported report are complete.
The order of the items is header → subline → tiles → rows, which is also the keyboard order (`flach`). New helpers:
`_cpu_kurz()`, `_mal()` (× in PCIe links), `_ohne_klammer()`, `_datum_lokal()`, `_edid()` (name and diagonal from the
detailed timing descriptor), `bildschirme()` (`kscreen-doctor -j`, fallback DRM modes), `sensor_titel()`.
`lire_specs()` gained `hero`, `sub`, `badges`, `kpis`, `rest` (the `lines` used by "Copy specs" and the inspector are
unchanged).

**QML:** `GlassPill` component and `win.accentInk`; per card `held` and `rollen` (indices per role, plain loops only –
see 5u); the hero header (selected while the header or one of its subline items is chosen; a click copies the full product
name), a KPI `GridLayout` (columns from the card width, even wrapping), a display-tile `GridLayout`, and in the row grid a
`raster` mode whose positions come from `hwWin.raster(items, zeichen)` (short values in pairs, a value longer than the
half column allows spans both; a hole on the right is filled by the next short value). The column width is derived from
the card width, not from the grid, so there is no binding loop. Rows show `d || v` and the full `v` in the tooltip.

**Found during the work:**
- At 820–1040 px in German the footer ("Speicherbänke lesen (Administrator)" plus the invisible copied label) made the
  root `ColumnLayout` lay out at 1037 px, so header, content and footer ran past the right edge. Reproduced with the
  committed 2.4.0 as well, so not caused by the refresh; fixed with an icon-only button below 1100 px and a shrinkable label
  (minimum now 787 px).
- Here `kscreen-doctor` names a different preferred mode id than the current one (the monitor runs at 2560 × 1440 and
  164 Hz), so the tile said "not preferred"; "Preferred" now compares the resolution, not the mode id.
- The PCIe "now" row was shown even when it equalled the maximum; it now appears only when the link is lower.

**Checks:** new window test 37/37 in Breeze Dark and Light (German, 1500 px) and 36/36 at 900 px: card pairs 0 px apart in
the overview, CPU, GPU, memory, storage and sensors tabs; tiles inside their cards; two hero headers in the CPU tab with
"AMD Ryzen 9 5900X" in 16 px bold and the subline; tiles "12C / 24T", "5,04 GHz", "64 MiB", "amd-pstate-epp" in one row;
the detail raster has two columns; ↓ selects the header, Enter copies "Model: AMD Ryzen 9 5900X 12-Core Processor", four
more ↓ reach the first tile and Ctrl+C copies "12 cores / 24 threads"; a click on a tile copies it; the kernel-module row
shows "620.73.04 · Open Kernel Module" and copies the full NVIDIA string; the API tiles read "OpenGL 4.6.0", "OpenGL ES
3.2", "Vulkan 1.4.363"; one display tile "2560 × 1440" copies "DP-3: …"; searching "5900X" keeps the hero header,
"vulkan" switches to the GPU tab. English at 820 and 1500 px: all checks except the test's own expectation of a decimal
comma. Window test 21/21 (Dark, Light), sensors 12/12 (Dark, Light) and 4/4 narrow, fan unit tests 9/9, window stress run
and main-window stress run (60 s, 5010 actions, 221 MB) without QML messages. `pyright` 0 errors, `qmllint` 0 warnings
outside *unqualified* (1304, analysed to line 6782 of 6847). All 12 `.po` files complete (515 entries).

**Not verified:** the real desktop with the user's colour scheme and icon theme (offscreen renders Breeze icons only);
refresh rate and scaling inside the window (offscreen `kscreen-doctor` cannot reach the compositor; verified from the
shell: DP-3, 164 Hz, 100 %); AMD and Intel GPUs (VRAM from sysfs, no power-limit or clock tiles); several displays side by
side; machines where `dmidecode` was run (memory speed and slot tiles).

## 5z. Optional live displays and monochrome toolbar icons (issue #4, after 2.4.0)

**Request (GitHub issue #4 by Sadi58):** make the title-bar monitor, the drive temperature and the drive I/O display
optional, offer monochrome toolbar icons, offer the system window decoration, and avoid the duplicate settings entry.
Agreed with the user: everything except the system window decoration, which needs its own work (frameless window, own
buttons, resize grips, blur region and corner radius are tied together; on Wayland the flags cannot be switched
reliably at run time).

**Implementation:** four new keys in `settings.json` – `title_monitor`, `drive_temp`, `drive_io` (default on: only
`false` turns them off) and `mono_toolbar_icons` (default off) – with the backend properties `titleMonitor`, `driveTemp`,
`driveIo`, `monoToolbarIcons` (one `displayPrefsChanged` signal, one `_anzeige()` setter, saved delayed like the other
settings). QML: `miniTele`, `tempChip` (and its part of the card's screen-reader name) and `ioArea` add the setting to
their `visible`; `QuickBtn` and `CompactBtn` take `barIconsMono[...]` (from `bar_icons_mono()`, resolved once in the GUI
thread: the first existing `-symbolic` name, else the normal icon) and draw it with `isMask` in the text colour. The
settings dialog has a "Monochrome toolbar icons" switch and a "Live displays" group with three check boxes; the title-bar
entry explains in a tooltip that it only appears while neither the inspector nor the ribbon panel shows the values.
The compact toolbar's "…" button and its one-item menu are removed; "Show and options" left the `.po` files.

**Not changed on purpose:** the sampling threads keep running when a display is off – the inspector (activity and
storage I/O), the ribbon telemetry and the drive properties use the same data.

**Checks:** new test 16/16 in Breeze Dark and Light: defaults on/off as above; no overflow button in the compact toolbar;
`Ctrl+,` opens the dialog with all four new controls, reachable with Tab; monochrome mode masks all 12 toolbar icons with
symbolic names (`document-properties-symbolic` … `user-trash-symbolic`) and switches back; temperature chips (5) and
I/O areas (3) disappear when switched off; the title-bar monitor appears in a 1000 px window and disappears when switched
off; the four keys are written to `settings.json` and read back. Settings test 20/20 (its Tab walk now takes 30 steps
because the dialog has four more controls), window test 21/21, hardware window test 37/37, main-window stress run 60 s
(4928 actions, 228 MB) without QML messages; screenshots of the ribbon and the compact toolbar in monochrome (Breeze Dark
and Light). `pyright` 0 errors, `qmllint` 0 warnings outside *unqualified* (1321, analysed to line 6810 of 6875); all 12
`.po` files complete (520 entries).

**Not verified:** monochrome icons with the user's own icon theme on the real desktop.

## 5aa. Pre-release audit for 2.5.0 (2026-11-28)

A structured audit before tagging: static analysis, the new features and their edge cases, design consistency in three
colour schemes, and a combined stress run. All harnesses run offscreen (section 7). Findings were fixed at once and the
affected checks run again; the numbers below are from the final run on the release state.

### 1. Static analysis

| Check | Result |
|---|---|
| `pyright` 1.1.414 | 0 errors, 0 warnings |
| `qmllint` on `--dump-qml` (6886 lines) | 0 warnings outside *unqualified* (1322, the known context-property pattern); a probe line with an unqualified access inserted at line 6885 of 6888 is reported, so the analysis reaches the end of the file |
| Translations (12 `.po` + English) | 508 entries each, 0 empty, 0 placeholder mismatches, every `.mo` identical to its `.po` (checked with `gettext`), 0 texts used by the code without a translation |

**Fixed:** 12 keys that the redesign of the hardware window left behind ("BIOS / UEFI", "Compatibility", "Date",
"Display server", "Instance version", "Logical CPUs", "Memory controller", "Outputs", "Running at", "Slots", "Version",
"{mode} (preferred mode)") were removed from all languages; "Show and options" (the old "…" menu) was already gone.

### 2. Features and regressions

**System information window** – all 8 categories at 1500, 1180, 900 and 820 px (VividViolet, English; German at 1500
and 1180): card pairs 0 px apart (top and height), one column at 900 and 820 px, nothing past the right window edge
(header, content, footer), no visible text with empty brackets or dangling separators – 25/25 (two columns) and 33/33
(one column) per width. Hero headers, tiles, keyboard (↓/Enter/Ctrl+C), search and copying: 37/37.
- **Finding, fixed:** at its own start size (1180 × 780) the window showed one column, because two columns began at
  960 px of content width and the content is 951 px wide there. The threshold is now 900 px.
- **Finding, fixed:** the hero title reserved a flat 190 px for the badges, so "NVIDIA GeForce RTX 4080 SUPER" and the
  mainboard name were cut at 1180 px. The title now subtracts the real badge width (computed from the card width, not
  from its own row – the first attempt caused a "recursive rearrange" loop, caught by the warning check) and shows the
  full name in a tooltip when it is still too long.

**Displays** – unit test 17/17 (together with the sensor and icon checks below): without `kscreen-doctor`, and with
garbage, empty, `null`, list-shaped or disabled-output answers, the DRM mode list is used; the screen text has no empty
parts and the resolution and connector pills are never empty.
- **Finding, fixed:** `kscreen-doctor` inherited DriveDeck's `QT_QPA_PLATFORM`. Started with a forced platform (xcb,
  offscreen) KScreen could not reach the compositor, so refresh rate and scaling were missing. The variable is now
  removed for that call; even the offscreen process now gets "DP-3 · 164 Hz · 100 %".

**Sensors & fans, read-only** – none of the old write paths exist (`PWM_ROOT_SKRIPT`, `pwm_schreiben`, `pwm_auftraege`,
`fan_bios`, `setFanPreset`); while reading all chips and the fan-control state only `nvidia-smi` and `systemctl` are
started and nothing under `/sys` is opened for writing; the sensor thread stops when the window closes.

**vnstat and the own traffic counter** – 20/20: fresh vnstat database without day values → own counter; created today →
own counter; created yesterday → today from vnstat, week and month from the own counter, mixed source line; 60 days old →
vnstat only; no vnstat or a broken answer → own counter; first run, growth, reload in the same boot (no double count),
reboot through `boot_id`, counter reset without a reboot; no temporary files left; a half-written `net_usage.json` is
replaced by a fresh start; four threads writing at once always leave valid JSON (`schreibe_atomar`: temp file, `fsync`,
`os.replace`).
- **Finding, fixed:** with the vnstat service stopped, `vnstat --json` keeps returning the old database and today, this
  week and this month froze. vnstat stamps every save (`updated.timestamp`, every 5 minutes, every 30 when all
  interfaces are offline); when the newest stamp is older than 45 minutes DriveDeck uses its own counter. Tested with
  1 h (own counter), 20 min (vnstat) and an old vnstat without the stamp (vnstat).

**Issue #4 options** – 20/20 in Breeze Dark, Breeze Light and VividViolet: defaults, no "…" button, all four controls in
the dialog and in its Tab order, live switching without restart, saved and read back from `settings.json`; while
temperature and activity are hidden on the cards both sampling threads keep running (checked after more than one 5 s
temperature cycle) and the inspector still has the values; switched on again, the chips appear at once. Monochrome
icons: with a theme that has no `-symbolic` icons the normal names are used (drawn as a mask), and with no icon at all
the last fallback name, never an empty source.

### 3. Design consistency and stress

**Contrast** (WCAG, computed from the scheme files with the same mixes as the QML):

| | Breeze Dark | Breeze Light | VividViolet |
|---|---|---|---|
| tile value | 13.99 | 13.10 | 9.74 |
| tile label (secondary) | 7.64 | 5.61 | 5.61 |
| row key on card | 8.55 | 5.86 | 6.17 |
| tile subline (tertiary) | 6.34 | 4.68 | 4.75 |
| accent value on API tile | 9.97 | 6.78 | 7.73 |
| accent badge text | 8.92 | 6.45 | 7.39 |

All ≥ 4.5 : 1. Radii stay on the token scale (cards 12, tiles and rows 8, pills half their height), dividers in the
window are the 1.5 px glass lines. **Fixed:** the device-symbol tile of the hero header used a radius of 10 px, off the
4/6/8/12 scale; it now uses the card radius (8 px).

**Window and keyboard tests in all three schemes** – window test 21/21, hardware window 37/37, sensors 12/12, settings
20/20 each (Tab chain, `Ctrl+,`, `Ctrl+F`, arrows, Enter/`Ctrl+C`, `Esc`); no `TypeError`, `ReferenceError`, binding loop
or "recursive rearrange" in any run (the only message is the harness's own "icon theme not found").

**Combined stress run** (VividViolet, 90 s): 421 random compound actions – opening the hardware window, switching
categories, searching, arrow keys and Enter, resizing it to 820–1500 px, closing it; opening the settings with `Ctrl+,`,
tabbing and `Esc`; toggling the five display settings; resizing the main window to 1000–2400 px. RSS 203–229 MB without
growth, no QML errors; after closing no worker thread is alive and the stop flag is set.

### 4. Previews

`preview.png` (main window, 2200 px), `preview-settings.png` (settings with the new options), `preview-specs.png`
(GPU & Display) and `preview-specs-cpu.png` (CPU & Board) were rendered offscreen with a copy of the desktop's colour
scheme, icon theme, fonts and Kvantum style, in English, with the placeholder IP 192.168.1.10; nothing was written to the
real configuration.

### Not verified

The real desktop with blur (the previews are opaque offscreen renders); X11 sessions; AMD and Intel GPUs; several
monitors; memory tiles after `dmidecode`; vnstat with a database that is weeks old on this machine (simulated only).

---

## 6. Not verified

These need a real desktop session and were **not** covered by the offscreen tests:
- Contrast ratios were judged on real screenshots (dark scheme and Breeze Light), not measured with a contrast tool.
- Real pointer behaviour: drag, resize at the window edge, hover and hit-testing, double click on the title bar buttons.
- Screen readers (Orca). Roles and names are checked in code and the Tab order with a scripted harness, but no screen
  reader read them aloud.
- Actually starting a terminal or file manager (the function test checks the command lines only).
- GPU overdraw and GPU load.
- Memory behaviour over many hours.
- The context menus of the drive, network and printer cards were only exercised by right-click scans (no warnings), not inspected visually. The export menu could not be opened because its dialog was closed.

---

## 7. How the tests were run

All harnesses set `QT_QPA_PLATFORM=offscreen`, `DRIVEDECK_NOBLUR=1`, `DRIVEDECK_MULTI=1`, patch `QApplication.exec`, capture QML
warnings with `qInstallMessageHandler`, stub `lancer`, and wrap `subprocess.Popen` to block privileged and launching
commands (since 5l an allowlist: only read-only tools such as `lsblk`, `lpstat`, `nvidia-smi` may run). Screenshots use
`grabWindow().save()`; real-desktop screenshots run DriveDeck with a stubbed launcher, capture the active window with
`spectacle -b -n -a` and end it with SIGKILL so that the saved window size is not touched. The exported QML
(`python drivedeck.py --dump-qml`) maps to `drivedeck.py` as: file line = dumped line + 4878 (at the time of 5l).