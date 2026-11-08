# Changelog – DriveDeck (fork of Fenestra "This PC")

DriveDeck is based on **Fenestra This PC 1.1** by [naykkalak](https://github.com/naykkalak/fenestra-ce-pc)
(GPL-3.0-or-later). All original copyright notices are kept. This file lists every change made in the fork,
as required by GPL-3.0 §5(a) (prominent notice of modifications).

The exact line counts are best taken from the GitHub diff against upstream. The program is still a single file, now called `drivedeck.py` (formerly `ce_pc_plasma.py`). `PyQt6.QtNetwork` is used when available (otherwise the
single-instance feature is skipped); **NumPy** is an optional dependency for the live I/O graph (without it the graph is
hidden and everything else works).

---

## 2.0.0-rc1 – 2026-11-08 (Release candidate)

First release candidate for 2.0.0: no new features are planned before the final release, only fixes.

### Added

- **Custom application name.** Right-click the title bar or the "This PC" heading (or click the small pencil that appears
  when you hover the header, or use *About → Application name*) to give DriveDeck any name, e.g. "Dieser PC" or
  "CyberDeck". The name is used in the title bar, the window title and the heading of the drive list; an empty name
  restores the defaults. It is also written to `Name=` in `~/.local/share/applications/drivedeck.desktop`, so the
  application menu and KRunner show it (and `update-desktop-database` is run afterwards).

### Fixed

- **Version check.** A release candidate is now newer than every beta (alpha < beta < rc < final). Before, `rc1` would have
  ranked below `beta.8.6` and never been offered as an update.
- **Pulsing usage bars.** The usage bars of drive and network cards did not pulse at the warning threshold because of a
  QML scope error (`ReferenceError: crit is not defined`).
- **Termination.** `kill`/logout (SIGTERM) and Ctrl+C (SIGINT) now close the window like the close button: the window size is
  saved and the background threads stop cleanly.
- **Atomic writes.** Every configuration and cache file is written to a temporary file, flushed to disk (`fsync`) and then
  moved into place, so a crash or power loss cannot leave a half-written file.
- **Properties dialog.** File system, mount point and device are elided with a tooltip when too long; the capacity legend
  uses layout sizes.

## 2.0.0-beta.8.6 – 2026-11-08 (Glass window)

### Added

- **Own title bar, no KWin frame.** The window is frameless and transparent: small app icon on the left, name in the
  centre, traffic-light buttons on the right (yellow minimise, green maximise/restore, red close). Dragging the bar moves
  the window, a double click maximises it, the edges and corners resize it. The corners are rounded (radius 12) and a
  thin edge outlines the window; both disappear when maximised.
- **Blur from the topmost pixel row.** Title bar, ribbon, content and footer are translucent and KWin blurs what is
  behind the whole window (rounded region, follows the window size). It uses `KWindowEffects` from KF6WindowSystem via
  `ctypes`. Without blur support (or with `DRIVEDECK_NOBLUR=1`) all surfaces stay opaque.
- **Pulsing warnings.** The CPU, RAM and Storage chips pulse red from 90 % (Storage: less than 10 % free), and the usage
  bars of drive and network cards breathe once the warning threshold is reached. The animations run only in the
  critical state.
- **Hover feedback.** Drive and network cards, the telemetry chips and the I/O sparkline scale up smoothly (1.03,
  150 ms). The chips get a thin cyan edge.
- **Neon sparklines.** Read is cyan, write is magenta, with a soft glow; while data is read or written the line
  transparency pulses.

### Changed

- The hard separator line below the ribbon is gone.
- Chip labels use 65 % opacity.

## 2.0.0-beta.8.5 – 2026-11-08 (UI polish)

### Changed

- **Readability.** Chips, badges, labels and section pills now use the normal system font; before they were set to 92 % of it (and
  the small system font as a floor), so nothing in the window is smaller than the text of your Plasma theme. The ribbon height
  scale is calibrated to match, so the layout with the standard font is unchanged.
- **Sidebar.** Rows are 32 px high (headings 40 px), folder icons 22 px and the tree arrow, the *+* button and the pin symbol use
  `Kirigami.Units` icon sizes (16 px / 32 px); the pin symbol has a 32 × 32 px click area and is easier to see (75 % when pinned,
  55 % on hover instead of 55 % / 35 %). Margins and the tree indent follow the 8 / 16 px grid; the hierarchy lines stay aligned.
- **Spacing on the 4 / 8 / 16 px grid.** Odd spacings in the cards, dialogs and sidebar (3, 5, 6, 10, 12, 14 px) now come from
  `Kirigami.Units.smallSpacing` / `largeSpacing`.

### Fixed

- With a larger system font the four telemetry chips and the read/write column on the drive cards now grow with the font, so
  "Storage" and "Network" are no longer cut off.

---

## 2.0.0-beta.8.4 – 2026-11-07 (installer fixes)

### Fixed

- **uninstall.sh was not executable**, so `./uninstall.sh` failed with "Permission denied". It is now, and it also rejects unknown options and understands `--help`.
- **`--purge` now also removes** the icon cache `~/.local/share/icons/drivedeck_cache`; the uninstaller refreshes the menu cache afterwards.
- **install.sh:** the desktop folder is looked up after the packages are installed (so a just-installed `xdg-user-dirs` is used and the shortcut goes to the right folder); a missing `sudo` gives one clear message instead of a failure for every package; `PyQt6.QtWidgets` and `PyQt6.QtQuick` are checked separately (Debian ships them in separate packages); `fstrim` is listed as an optional program.

---

## 2.0.0-beta.8.3 – 2026-11-06 (new ribbon, audit fixes, cleanup)

### Changed

- **Cleanup.** Removed dead code found by an audit: the unused `clickMode` / `setClickMode` backend API (the click mode is read from
  `settings.json`), an unused icon entry, three never-referenced QML ids, stale comments and three unused SVG files in `icons/`.
  The system-centre info card gets a little more air on its left so it sits closer to the middle.
- **Ribbon spacing and hover from the Plasma theme.** Margins, gaps, radii and icon sizes in the ribbon (buttons, group separators,
  *Show* grid, warning-threshold popup, system info card, telemetry chips) come from `Kirigami.Units` on the 4/8/16 px grid
  (`smallSpacing`, `largeSpacing`, `iconSizes`) instead of fixed pixels, so they follow the system font and scale setting. Hover and
  press on the ribbon buttons and on *Warning threshold…* use the theme's highlight colour at 15 % / 30 % with `smallSpacing`
  corners. No fixed `font.pixelSize` is left; texts use the system fonts (`badgeFont`, `Kirigami.Theme.defaultFont`).
- **Ribbon in four groups, read from left to right.** *Navigation* (Properties, Open, Refresh, Add a network location; the
  former *Location* and *Network* groups are merged) · *Show* · *Actions & tools* (System monitor, Analyze storage, SSD optimization,
  Trash with its size, Terminal; the former *Tools* and *Quick actions* groups merged) · *System centre*
  (System information, System Settings, About, a card with the distribution logo, uptime, installation date, host, kernel and Plasma, sized so
  its longest line is shown in full, and at the far right the four-chip telemetry panel that stretches to the right edge). All buttons are one component (`QuickBtn`)
  with the same hover highlight. If the system centre has little room, the distribution card is dropped first (window below
  about 1990 px), then the telemetry panel (below about 1710 px); the two buttons always stay. The sidebar edge still lines
  up with the first separator, which is now after the four *Navigation* buttons, so the sidebar is wider than before.

### Fixed

- **No more waiting in the window for external programs.** *Print test page*, *Set as default printer* and starting a scan
  program (which may call `flatpak info`) now run in the background, so a stuck CUPS or Flatpak can no longer freeze the
  window for up to 15 seconds. Whether a scan program exists is remembered for 30 seconds instead of being looked up for
  every scanner card again. The unused `getLabel` function was removed.
- **Trash size:** the time limit now also covers listing the first level of the trash, so a trash with a huge number of files
  cannot hold the background thread up.
- **Ribbon and larger fonts.** The height of the ribbon, its buttons and the summary chips now follows the line height of
  the system font (unchanged with the standard font), so captions are no longer cut off with a larger font size.
- **Narrow windows.** The window no longer has a minimum width of about 1220 px. Below that the ribbon can be scrolled
  sideways (mouse wheel, drag or the thin scroll bar under it). The groups to the right of *Show* still appear only when
  there is room, as before.
- **SSD optimization** now runs `fstrim` under `timeout` (as root), so after 15 minutes the program itself is stopped and not
  only the password helper; a message says so.
- The settings file is written to disk (`fsync`) before it replaces the old one.
- **Spacing and fonts.** The gaps beside the ribbon separators come from `Kirigami.Units` (16 px), the ⚠ and the About
  title use the system font size instead of fixed pixels, and the lines of the system info show their full text in a tooltip
  when they are shortened.

---

## 2.0.0-beta.8.2 – 2026-11-06 (click mode, update check)

### Changed

- **Click mode also reads the system-wide default.** If `~/.config/kdeglobals` has no `SingleClick` entry, DriveDeck now looks
  at `/etc/xdg/kdeglobals` (the default a distribution sets for all users); the user's own entry still wins, and without any
  entry the double click stays the default. Taken from the patch that Sadi58 sent for the single/double-click request.
- The settings file is `settings.json` (it was `einstellungen.json` in 2.0.0-beta.8; an old file is taken over automatically).

### Fixed

- **Update check with versions like `beta.8.2`.** Only the first number after `beta.` was compared, so `2.0.0-beta.8.2`
  counted as the same version as `2.0.0-beta.8` and nobody would have been told about it. All numbers count now.

### Other

- `APP_VERSION` is `'2.0.0-beta.8.2'`; the *About* dialog shows it.

---

## 2.0.0-beta.8 – 2026-11-06 (ribbon, click mode, warning threshold)

### Added

- **Click mode** (feature request "Compatibility with global single/double click setting" by Sadi58). Folders, drives, network locations and the cards in "Printers and devices" open with a **double click**
  by default. One click is used only if the desktop explicitly says so (`[KDE] SingleClick=true` in `kdeglobals`; on
  other desktops Qt's `QStyleHints`). A missing or unreadable entry means double click. `~/.config/drivedeck/settings.json`
  can force it with `"click_mode": "system"` (default), `"double"` or `"single"`. The setting is read again whenever the
  window gets focus; a double click never opens a second window in single-click mode.
- **Adjustable warning threshold** (feature request "Free space warning threshold setting" by Sadi58) in the ribbon group *Show* ("Warning threshold…" at the bottom of the second column, opens a small slider window): 1 to 50 %, default 20 %, saved
  as `"warn_threshold_percent"` in the same file. It replaces the fixed 80 % used space for the red gauge and the warning
  badge and applies immediately. The system summary now hides below about 1540 px (was 1460 px).
- **The right end of the ribbon is no longer empty.** Two new groups sit between *Show* and the system summary, which now
  stretches to fill the free width at the far right. They appear only when the window is wide enough (the summary goes
  last, then *System info*, then *Quick actions*) and never raise the window's minimum width:
  - **Quick actions:** *Trash* (opens `trash:/`; shows the size of `~/.local/share/Trash`, read in the background every
    minute with a time limit, `≥` if it is huge), *Terminal* (moved here from *Tools*), *SSD optimization* (`pkexec fstrim
    --all --verbose` after a confirmation; the result is shown in a message).
  - **System info:** the logo of your distribution in its original colours (the icon named by `LOGO=` in `/etc/os-release`,
    else the usual `distributor-logo-<id>` files), plus uptime, installation
    date (approximate: the oldest birth time of `/etc/machine-id` and `/`), host name with distribution and version, and
    kernel and Plasma version.

### Fixed

- **Message boxes** (for example the SSD optimization result): the OK button no longer overlaps long text.

### Other

- The settings file is called `settings.json` (an `einstellungen.json` from an earlier build is taken over automatically).
- `APP_VERSION` is `'2.0.0-beta.8'`; the *About* dialog shows it. `preview.png` was rendered again (2200 px wide, so the new
  ribbon groups are visible).

---

## 2.0.0-beta.7 – 2026-11-02 (robustness on other hardware)

### Fixed

- **Whole disk of a device** (SMART, safe removal): now resolved through sysfs, so virtual disks (`vda`, `xvda`, `hda`) and
  LUKS / LVM / RAID volumes no longer run `smartctl` or `power-off` on a partition or mapper device. Without a sysfs entry
  the name patterns now also know `vd*`, `xvd*` and `hd*`.
- **Ink colours of other makers**: cartridge colours given as names (`cyan`, `magenta` …) instead of `#RRGGBB`, as allowed by
  the IPP standard, are now shown in colour; otherwise a colour word in the cartridge name is used, last resort grey.
- **Graphics card without `lspci`** (no `pciutils`): vendor and driver are read from `/sys/class/drm` (cached values only,
  they do not wake a sleeping GPU). The exact model name still needs `lspci`.
- **Processor name on ARM** (no `model name` in `/proc/cpuinfo`): taken from `lscpu`, then the device tree.

---

## 2.0.0-beta.6 – 2026-11-02 (context menus, Skanpage fix)

### Added

- **Right-click menus in "Printers and devices".** Printers: *Properties*, *Set as default printer* (only if it is not the
  default yet, `lpoptions -d`, no administrator rights), *Print test page* (only if online), *Open settings*, *Copy name*.
  Scanners: *Scan…* and *Copy name*. Keyboards, mice, gamepads: *Open settings* (matching System Settings module) and
  *Copy name*. Only names of printers that DriveDeck itself shows are passed to `lp` / `lpoptions`.
- The test page is the real CUPS test page: the `testprint` banner template is sent with
  `document-format=application/vnd.cups-pdf-banner`, so CUPS fills in printer name, driver, job ID etc. (needs `lp` and
  the `bannertopdf` filter from cups-filters).

### Fixed

- **Skanpage not found.** Double-clicking a scanner showed "Program not found" when Skanpage is installed as a Flatpak.
  DriveDeck now tries `skanpage`, `flatpak run org.kde.skanpage` (detected via the exported `.desktop` file or
  `flatpak info`), `simple-scan`, `kooka`, `xsane`, and shows the message only if none exists (with a hint to install
  `skanpage` or `simple-scan`).

---

## 2.0.0-beta.5 – 2026-11-02 (new system summary)

### Changed

- **New look for the system summary.** The three thin bars and the lone network pill are replaced by four telemetry chips
  in a 2 × 2 grid inside a softly tinted panel (the card glow, toned down: purple → blue → cyan). Every chip has an icon
  from the icon theme and a name (**CPU**, **RAM**, **Storage**, **Network**), the value in the fixed-width font so the
  digits do not jump, and a thin usage bar in the purple-to-cyan gradient (amber from 80 %, red from 90 %). The network
  chip shows `▲ 2.4K/s  ▼ 3.2K/s` in two colours (full values in the tooltip); a value that is too wide for its chip is
  scaled down instead of overflowing. On narrow chips only the used part is shown (`9.0 GB` instead of `9.0 / 29.2 GB`).
  The group still has no preferred width and still hides below ~190 px.
- The chips are created once; only their texts and bars change (and only when a value changes) instead of rebuilding all
  chips every second. `preview.png` was rendered again.
- `APP_VERSION` is `'2.0.0-beta.7'`; the *About* dialog shows it.

---

## 2.0.0-beta.4 – 2026-11-01 (ink levels)

### Fixed

- **Wrong ink levels.** DriveDeck asked CUPS first and only asked the printer itself when CUPS knew nothing. The values CUPS
  keeps for a queue come from the last job or a driver and can be stale or wrong (for example 60 / 0 / 0 / unknown instead of
  the real 99 / 26 / 23 / 24 %, with the yellow cartridge missing). The printer is now asked directly first
  (`ipp://<address>:631/ipp/print`) and CUPS is only the fallback, for example when the address is unknown or the printer does
  not answer. The result is still cached for 20 s.

### Notes

- `APP_VERSION` is `'2.0.0-beta.4'`; the *About* dialog shows it.

---

## 2.0.0-beta.3 – 2026-10-29 (read/write speed on the drive cards)

### Changed

- **Read/write speed as numbers on the drive cards.** Below the I/O sparkline two compact labels show the current rates:
  green ▼ for reading, ▲ in the theme's neutral colour (as the write line) for writing, in the fixed-width font so the digits do not jump. Below 1 MB/s the value is
  shown in whole KB/s (`0 KB/s` when idle), from 1 MB/s on in MB/s, from 1 GB/s on in GB/s with one decimal. A drive without
  values shows `-`. The values still come from `ioStats`; the texts are separate string properties, so a label is only
  touched when its text really changes.

### Notes

- `APP_VERSION` is `'2.0.0-beta.3'`; the *About* dialog shows it. `preview.png` was rendered again.

---

## 2.0.0-beta.2 – 2026-10-28 (clean shutdown)

### Fixed

- **Clean shutdown.** Closing the window within the first seconds could end with a crash report (`SIGABRT`): a background
  thread looked up an icon (`QIcon`) while `QApplication` was being destroyed. Icon names are now resolved once at start in
  the GUI thread and background threads only read the cache. All background loops stop through a shutdown event, are
  joined for at most 0.6 s, `QApplication` is destroyed last, and the process exits right after cleanup instead of waiting
  for pending printer/hardware probes.

### Notes

- `APP_VERSION` is `'2.0.0-beta.2'`; the *About* dialog shows it.

---

## 2.0.0-beta.1 – 2026-10-28 (DriveDeck: new name, modern look and monitoring)

### Renamed to DriveDeck

- **New name and icon.** The program is now called **DriveDeck**, with its own icon (`assets/`, generated in all sizes by
  `assets/make_icons.py` from `drivedeck-source.jpg`: rounded corners, 16 to 512 px). The window title, the *About* window,
  the menu entry (`drivedeck.desktop`, `Icon=drivedeck`), the application id (`drivedeck`, so Plasma matches window and
  icon under Wayland), the single-instance name and the log prefix use the new name. The original authorship of
  naykkalak is kept in the file header, the *About* window, the README and `COPYING`.
- **File renamed** `ce_pc_plasma.py` → `drivedeck.py`. All internal leftovers of the old name are gone: the settings
  migration, the old-command forwarder in `install.sh`, the old language and icon-cache folders, the `ce-pc` translation
  catalogue (now `drivedeck.po`/`.mo`), the `CEPC_*` environment variables (now `DRIVEDECK_*`), the Dolphin bookmark tag
  (now `drivedeck-`) and the KWallet folder (now `DriveDeck`). **Network passwords saved by the old name must be entered once
  again**, and bookmarks added earlier stay in Dolphin's *Remote* section as normal entries. The original authorship of
  naykkalak stays in the file header, the *About* window, the README and `COPYING`.
- **Own folders.** Settings: `~/.config/drivedeck/`, caches: `~/.cache/drivedeck/`, data: `~/.local/share/drivedeck/`.
- The language files are also found next to the program (start from the project folder without installing).

### New features

- **System specs window.** The *System information* button in the *System* group opens a window with six tabs (*Overview*, *CPU &
  Board*, *GPU & Display*, *Memory*, *System & Drivers*, *Network*). Sources: `/proc`, `/sys`, `lspci -vmmk`, `lscpu`,
  `nvidia-smi`, `glxinfo`, `vulkaninfo`, `pactl`, `pw-cli`. The sections are collected in parallel by `lade_bericht()` in a
  background thread, shown with a busy indicator and cached for the session; a missing program only removes its rows.
  *Copy specs* copies a compact English summary, *Export full report…* writes text or JSON (with all loaded kernel
  modules). The RAM type, speed, slots, manufacturers and the CPU socket come from SMBIOS and need root: the button
  *Read slot details (administrator)* runs `pkexec dmidecode` (once at a time; cancelling is silent). The VRAM type is
  not exposed by drivers; for GDDR6X cards it is derived from the model name and labelled as such.
- **System summary chips.** Four compact telemetry chips (CPU %, RAM used/total, Storage used/total of all mounted
  local drives, network ▲/▼ rates) in the free space right of the *Show* group. A `_statsLoop` thread reads
  `/proc/stat`, `/proc/meminfo` and `/proc/net/dev` once per second (no process is started; rates are counter
  differences; only real network cards are counted, so bridges, veth and VPNs are not counted twice) and pauses with
  the window. The group has no preferred width, so the minimum window width stays the same; it hides below ~190 px of
  free ribbon space.
- **Unmount.** `unmountDevice` (`udisksctl unmount`) in the drive context menu, without powering the drive off. Hidden
  for system mount points and optical drives; errors (e.g. a file is still open) are shown in a message.
- **Tools group in the ribbon.** *Terminal*, *System monitor* (`plasma-systemmonitor`, else `btop`/`htop` in a terminal)
  and *Analyze storage* (`filelight`, else `baobab`, else `ncdu -x` in a terminal). Buttons only appear for installed
  programs (`backend.tools`); programs are started through a fixed table (`WERKZEUGE`) via `launchTool`, never from
  free text. *Analyze storage* is also in the right-click menu of drives, folder cards and the Quick access pane and
  analyses exactly that path (`/` really means `/`). The ribbon, and with it the minimum window width, is wider now.
- **Live I/O graph per drive.** A small sparkline on every mounted drive card shows read (green) and write (yellow)
  throughput of the last 60 seconds; the tooltip shows the current values (▼ read, ▲ write). A background thread
  (`_ioLoop`) reads `/proc/diskstats` once per second, turns the counter differences into bytes per second with NumPy and
  smooths them (`glaetten`, triangular 5-point window, edge-corrected). The scale is at least 1 MB/s so idle noise
  does not look like load. Device paths such as `/dev/mapper/…` are resolved to their kernel name. The data is a
  separate property (`ioStats`) so the disk list is not rebuilt every second (see bug fix 3).
- **"Almost full" warning.** From 80 % usage on (`alertFrac`, fixed in the code), the usage bar and the ring turn red and
  the card shows a badge such as "⚠ 90 %" with the tooltip "Almost full". German text included. (A ribbon button with a
  slider to change the level was built and removed again: it did not fit the design.)

- **Disk temperature.** A small chip with the current temperature (e.g. "46 °C") sits next to the name on the drive
  cards, and the *Properties* window shows it with one decimal. A background thread reads it every 5 seconds from the
  kernel sensor (`/sys/block/<disk>/device/hwmon*/temp1_input`: NVMe, and SATA drives with the `drivetemp` module);
  without such a sensor it asks udisks for the SMART value (cached for a minute). Partitions, LUKS/LVM volumes and
  unmounted volumes are mapped to the physical disk. The chip turns amber and red from 45 / 55 °C for spinning disks
  and from 65 / 75 °C for SSDs and NVMe drives. Drives without any sensor (many USB enclosures) simply show no chip.
- **Keyboard navigation through every area.** Before, the arrow keys only moved inside *Devices and drives* and *Network
  locations*. Now they cover the folder cards, drives, network locations, printers/devices **and the sidebar**
  (`navSections()`, `moveMain()`, `sideMove()` …). *Left* in the first column enters the sidebar, *Right* on an entry without
  sub-folders (or *Tab*) returns; in the sidebar *Right* unfolds a node and then selects its first child, *Left* folds it or
  selects the parent; *Enter* opens (like a double-click: folder, drive, printer dialog, scanner, or the System Settings page of a
  device), *Space* unfolds, *Home*/*End* jump to the first/last entry, *Ctrl+C* copies the path. The selected card is scrolled into view
  (`revealItem()`), folder cards now show a selection, and the sidebar shows which area the keys act on (outlined = active,
  faint = inactive). Duplicate entries (e.g. two folder cards pointing to the same path) are skipped by the keys, and the default
  Quick access pins no longer contain the same folder twice or the home folder itself (an XDG folder switched off to `$HOME`).
- **Quieter terminal.** Some icon themes (e.g. Vivid-Dark-Icons) contain SVGs with missing gradients, which made Qt print
  `qt.svg: Could not resolve property …` at every start. The program now switches only that one message category off
  (`QT_LOGGING_RULES=qt.svg.warning=false`); rules set by the user are kept and take precedence.
- **Jump to the matching System Settings page.** Double-click (or right-click → *Open settings*) on a device card in
  *Printers and devices* opens System Settings directly at the right module: game controller → `kcm_gamecontroller`,
  keyboard → `kcm_keyboard`, mouse → `kcm_mouse`, touchpad → `kcm_touchpad`, graphics tablet → `kcm_tablet`. Printers keep
  the *Properties* dialog on double-click and get *Open settings* (`kcm_printer_manager`) in the menu when
  print-manager is installed. Only a fixed list of modules can be opened (`SETTINGS_MODULES`); a module that is not
  installed is not offered. The device type is now part of the device data (`kind`).
- **Ink levels on the printer card.** A small bar chart right on the card shows every cartridge (up to four or more
  bars, in the ink's own colour, filling from the bottom with an animation); black ink uses the theme's text colour so it
  stays visible on dark themes, and a red outline marks a cartridge below its low-level mark. The tooltip lists the
  exact percentages. No need to open *Properties* any more. Hidden while the printer is offline.

- **Quick access sidebar with pinned folders** (like the navigation pane of the Windows Explorer). A left pane lists
  your pinned folders with a pin symbol; click opens the folder in Dolphin, the pin symbol (or right-click → *Unpin*)
  removes it, right-click also offers *Open in terminal*, *Copy path*, *Move up* and *Move down*. Pin folders from
  the **right-click menu of the folder and drive cards** (*Pin to Quick access*), with the **+** button (folder
  dialog) or by **dragging a folder from Dolphin** onto the pane. Pins of a USB stick are greyed out while it is not
  plugged in. On the first start Desktop, Downloads, Documents and Pictures are pinned. The list is stored in
  `~/.config/fenestra/ce-pc-epingles.json`; the pane can be hidden with the new check box *Quick access* in the
  ribbon group *Show* (the state is remembered like the other sections). The list can be collapsed with its arrow.
  The folder cards also got a right-click menu (*Open*, *Open in terminal*, *Copy path*, pin).
- **Drive tree in the sidebar** (like the tree view of the Explorer): under *This PC* every mounted drive is listed;
  a click on a drive or folder expands it, a click on the arrow or the node again collapses it, double-click opens it
  in Dolphin. Sub-folders are read **only when a node is expanded**, in a background thread (`listDirs`, hidden folders
  are skipped, at most 1000 entries per folder), with a small spinner while loading and thin guide lines per level.
  The arrow only appears on folders that really have sub-folders: when a folder is listed, the thread also checks every
  child with an early exit (`hat_unterordner`, 2 s time budget; unknown counts as "has sub-folders"), and drive roots are
  read at start-up.
  The clicked row stays highlighted (accent tint and outline) until another one is clicked; the hover highlight covers the
  whole row, not only the icon (a label swallows hover events, so the row uses a `HoverHandler` instead of a `MouseArea`).
  Expanding or collapsing keeps the scroll position of the list.
  The right edge of the pane lies exactly on the first vertical line of the ribbon (next to *Refresh*), so both form one
  continuous line; the width follows the ribbon (`sideWidth`), also with another language or font size.
  Every node can be pinned to Quick access with its pin symbol or the right-click menu. The system drive expands to
  the home folder, exactly like opening its card.
- `pin_normaliser`: pins are compared with `~` expanded and trailing slashes removed; symbolic links are **not** resolved
  on purpose (a pin keeps the path you chose, a stick mounted at another path stays a separate entry); case counts.

### SMART

- USB drives: if `smartctl -a` fails with a SCSI/identity error, DriveDeck retries automatically with SAT
  (`-d sat -T permissive`) and then the NVMe bridge modes (`nvme`, `sntjmicron`, `sntasmedia`, `sntrealtek`). USB drives
  start with SAT directly. If no mode works, the dialog explains that the enclosure does not support SMART pass-through.
- When root rights are needed, the whole fallback chain runs in a single `pkexec` session, so the password is asked once.

### Look

- Section headers ("Folders", "Devices and drives", …) are now upper-case with wider letter spacing, show the item count
  as a small accent pill and continue with a line that fades out to the right (new `SectionTitle` component).
- One hover/selection look for all cards (folders, drives, network locations, printers and devices): a new `CardGlow`
  component draws a translucent purple-to-cyan gradient with a glowing border; selected or pressed cards glow stronger.
  This replaces three separate highlight rectangles, one of which used a grey border.
  The border is a gradient ring (purple → blue → cyan, drawn as a `Shape` with the curve renderer) instead of a single colour.
- Readability pass (UI/UX audit): the small Plasma system font (often only 7 pt) is no longer used for labels. Card
  subtitles use the normal system font, ribbon labels, chips and badges at least 92 % of it. Secondary text is at least
  75 % opaque (better contrast on light themes). Section headers and card grids sit on an 8 px grid (24/16 px margins),
  the fold arrows have a 32 px click area, ribbon buttons are at least as wide as their longest word, and the *Storage* chip
  shows the full value. The minimum window width grows by about 40–90 px.
- Softer dividers: the line between sidebar and content and the ribbon group separators are fainter.

### Performance and robustness (review pass)

- Final refinements: `_agesa()` skips `dmesg` when `kernel.dmesg_restrict=1` and reports "not exposed by the kernel"; NumPy
  is imported once at module level (`HAS_NUMPY`) instead of inside the 1 s loops; the CPU chip guards the empty first
  state of `sysStats` in QML.
- Shutdown order: the QML engine is now deleted before the backend, and all QML reads of `backend` properties are guarded
  (`backend && backend.x`), so closing the window no longer logs "Cannot read property … of null".
- Pre-release audit (timeouts, paths, VMs, threads): subprocess error handlers now catch every `OSError`/`SubprocessError`
  instead of only "not found" and "timed out"; `openFolder` falls back to `xdg-open` on any `OSError`; `openTerminal`,
  "Analyze storage" and pinning check folders with a 2 s limit (`ist_ordner`) so a dead NFS/SMB mount cannot freeze the
  window; the System information overview, the memory trim and the update settings are protected against concurrent
  access; `lsblk` output with `"blockdevices": null` no longer raises.
- External programs (system monitor, terminal, Dolphin, analyzers, system settings) are now started fully detached: a
  short-lived shell puts them in the background, so they no longer appear as child processes of DriveDeck.
- Disk temperature: drives without a kernel sensor or udisks value (typically USB NVMe/SATA enclosures) are now also read
  with `smartctl -A` (SAT and NVMe bridge modes, NVMe/SCSI/ATA formats), in the background and cached. This works only where
  `smartctl` may run without root; there is no password prompt for it.
- Final audit pass: the disk, I/O, temperature and update loops now survive a single failing iteration instead of ending
  silently; thread errors print one line instead of a traceback; `/proc/mounts`, `/proc/diskstats` and `/proc/net/dev` are
  read tolerant of invalid UTF-8; a race on the NAS free-space cache is gone; the I/O and temperature loops only signal
  the interface when their values change; the `smbclient` free-space timeout is 20 s.
- **Memory trimming.** `gc.collect()` plus glibc `malloc_trim(0)` run in a background thread (`Backend.trimMemory`, at most
  one run at a time and not more often than every 5 s) and then trim the QML component cache. Triggers: after the
  hardware report is built, when the *System information* window closes, and shortly after the main window is minimized.
  Without glibc the call does nothing.
- The *System information* button now opens the hardware window directly; the separate *System specs* button and the
  KInfoCenter launcher are gone.

- Review of the new code: invalid UTF-8 in DMI/`/proc` text no longer empties the overview (`errors="replace"`); an
  `Unknown` RAM speed, an empty EFI variable and cache entries without `device` no longer abort a section or stall the
  live summary; a failed read shows an error card instead of an endless spinner; only one `pkexec` prompt at a time;
  `backend.tools` is computed once; module versions come from sysfs without a `modinfo` process per module; icon names for
  the hardware tabs are resolved in the GUI thread; the unmount thread reports every `OSError`; CPU load is clamped to 0–100 %.
- Background polling (drives, network, printers, temperatures, live I/O) now sleeps while the window is minimised or
  hidden and refreshes immediately when it is shown again.
- A dead NFS/SMB mount can no longer freeze the network list: `statvfs` is limited to 4 s and never stacked.
- Pinned folders are checked for reachability in the background, so an unreachable network pin cannot block startup.
- The live I/O graph only updates the UI when values change; kernel-name lookups are cached and only the displayed
  drives are sampled.
- The drive cache is written at most once a minute unless the drive list changes (fewer SSD writes).
- The smoothing kernel is computed once per series length.

### Visual changes

- **Donut ring** instead of the pie chart in the *Properties* dialog (`QtQuick.Shapes`, GPU curve renderer): rounded
  ends, percentage in the centre, animated fill, smooth colour change at the warning level.
- **Slimmer, fully rounded usage bars** (10 px, no frame) that animate to the current value, also when a window opens.
- **Softer card hover:** rounded corners, fade in/out, light tint on hover, accent colour and a thin accent strip on
  the selected card; the icon grows slightly under the mouse (drives, network locations, printers).

### Notes

- New optional dependency: **NumPy** (imported once at module level, `HAS_NUMPY`; without it the I/O graph is hidden). `install.sh`
  installs it when you agree.
- Checked with a small test harness that loads the QML and listens to the engine warnings (0 warnings), plus
  screenshots of the rendered window. The harness is not part of the repository.
- A search/filter across all cards was tried and removed again: it only searched inside this window and added little.

## 1.2.0 – 2026-10-25

*Historical entry: paths and names below refer to the program before the rename to DriveDeck.*

## Bug fixes

| # | Problem in the original | Fix |
|---|---|---|
| 1 | On Btrfs systems `lsblk` reports only one of several mount points per device (e.g. a subvolume such as `/var/tmp`). Double-clicking "Local Disk" therefore opened `/var/tmp` instead of the user's files, and the system drive was not recognised as `/` (sorting, root icon, `DRIVEDECK_SANTE_TEST` health test). | `lsblk` is queried with `MOUNTPOINTS` (plural, falls back to `MOUNTPOINT` on old util-linux). If a device has several mount points, `/` wins, otherwise the first non-system one. The system drive keeps the mount point `/`; `/` and `/var/tmp` open the **current user's home** (`os.path.expanduser("~")`) via the new helper `chemin_affiche()`. Works for every user and needs no hard-coded path or device. |
| 2 | Mount-point prefix check used a plain `startswith`, so `/bootdisk` or `/sysdata` were hidden because of `/boot` and `/sys`. | New `ignore_mount()` compares whole directories. `/var` is ignored for local disks only (`DISK_IGNORED_PREFIXES`). |
| 3 | The disk list was replaced on every byte change of used/free space (about every 3 s on the system drive). QML rebuilt all cards, closed the context menu and made the hover flicker. | Comparison uses only what is displayed (`_signature_disques`), ignoring raw `used`/`free`/`total`. |
| 4 | Network mounts with spaces (`//nas/My Share`) were not matched because only the mount point, not the device field, was unescaped (`\040`). The entry appeared twice. | The device field of `/proc/mounts` is unescaped as well. |
| 5 | Update banner showed a false update for `1.1.0` vs `1.1` (`(1,1,0) > (1,1)` is `True` in Python). | `_version_tuple` pads with zeros. |
| 6 | `_USB_CACHE` was never cleared: a different stick that became `/dev/sdb` later inherited the old USB result. | Removed. `TRAN` and `RM` are read in the same `lsblk` call and passed down from the disk to its partitions. |
| 7 | "No label" was detected by comparing with the translated text `"Local Disk"`. A disk really named that (or a colliding translation) was renamed; the rename field started with "Local Disk". | Empty label = no label. The fallback text is applied only at the end; the rename field starts empty. |
| 8 | Race condition in `sync_places()`: the startup thread and add/remove could write the same `.fenestra.tmp` at once. | `_PLACES_LOCK` around the function body. |
| 9 | `smbclient -U user`: the user regex allowed `%`, which `smbclient` reads as `user%password`. | `%` is rejected in user names. Redundant `if user` checks in `addNetwork` removed. |
| 10 | Zombie processes after `Popen` (Dolphin, `xdg-open`, apps) until the next `Popen`. | New `lancer()` starts programs detached (`start_new_session`) and reaps them in a small thread. |
| 11 | If `scanimage` is not installed, `detecter_scanners()` returned `[]` and triggered 10 pointless quick retries. | Returns `None` in that case; the previous result is kept. |
| 12 | `open(...).read()` without `with` for the SVG/icon files. | `_lire_texte()` helper with `with`. |
| 13 | Fragile QML: `parent.parent.frameWidth` in the folder delegate. | `folderGrid.frameWidth`. |

## Performance and robustness

- **No more blocking in the GUI thread.** `lsblk`, `udevadm` and the `busctl` SMART calls (up to 3 s each) now run in
  their own thread (`_diskLoop`). The window no longer waits for them at start-up.
- **Separate threads for disks, network locations and printers/devices.** A dead NAS no longer delays the printer list.
- **Parallel probing** with `ThreadPoolExecutor`: network locations (`host_reachable`, `net_espace`) and printers
  (`imprimante_repond`, avahi lookup, ink levels). KWallet access is serialized with `_WALLET_LOCK`.
- **One `lsblk` call per refresh** instead of one call per disk for `TRAN` and `RM`, and no more reads from `/sys`.
- **Event-driven refresh.** Every second only a hash of `/proc/self/mountinfo` and `/proc/partitions` is read.
  The full read runs only when something changed (device plugged in/out, mounted/unmounted) or every 10 s for the
  free-space values (`DISQUES_INTERVALLE`). Fallback to a 3 s interval if `/proc` cannot be read.
- **Disk cache** (`~/.cache/fenestra/ce-pc-disques-cache.json`): drives appear immediately at start, like the network
  and printer caches.
- **Icon lookups cached** (`QIcon.hasThemeIcon` result per icon name).

## New features

- **Unmounted volumes are shown.** Data partitions that are not mounted (second internal disk, Windows partition,
  stick that was not auto-mounted) appear as a card "Not mounted · size". Double-click or right-click **Mount**
  mounts with `udisksctl` (Plasma may ask for authentication on internal disks) and opens Dolphin.
  Hidden: swap, LUKS, LVM/RAID, EFI/recovery and other fixed partitions under 1 GiB. No gauge and no "Properties"
  for these cards.
- **Disk context menu:** *Mount*, *Open in terminal*, *Copy path*.
- **Network context menu:** *Disconnect* (`umount` for mounted shares), *Open in terminal*, *Copy path*.
- **Keyboard control:** arrow keys select a drive or location, `Enter` opens, `F5` refreshes, `Esc` clears the
  selection, `Ctrl+C` copies the path of the selection.
- **Single instance:** a second start brings the existing window to the front (local socket
  `fenestra-ce-pc-<uid>`). `DRIVEDECK_MULTI=1` allows several windows for testing.
- **QML development mode:** `python3 drivedeck.py --dump-qml > drivedeck.qml` writes the UI to a file;
  `DRIVEDECK_QML=drivedeck.qml python3 drivedeck.py` loads it from there. The default stays a single-file install.
- **German texts** for all new menu entries and messages as built-in fallback (`EXTRA_DE`), used when the gettext
  catalogue has no translation. Other languages show English until a `.mo` entry exists.

## Fork-specific changes

- **Application identity** (`setApplicationName` / `setDesktopFileName` = `fenestra-ce-pc`): Plasma now matches the
  window to `fenestra-ce-pc.desktop` under Wayland, so the task bar shows the right icon and name instead of `python3`.
- **Update check disabled** (`MAJ_API = ""`, `MAJ_PAGE = ""`). Otherwise the banner would point to the upstream
  repository and suggest overwriting the fork. The checkbox in the About dialog is hidden while no URL is set;
  set your own repository URLs in the code to re-enable it.
- File header and `APP_AUTEUR` mention the fork and keep the original copyright.

## Removed (dead code)

`go()` (Python and QML), `BAR_ICONS`, `bar_icons()`, the slot `barIcon`, the context property `barIcons`,
the refresh `QTimer`, `get_mount_label`, `is_removable`, `is_usb_connected`, `_USB_CACHE`,
and the duplicate user checks in `addNetwork`.

## Known limitations

- Drive temperature of USB enclosures (and SMART from the background) needs `smartctl` without root; otherwise only the SMART
  dialog shows it.
- Not tested: AMD/Intel graphics and Wi-Fi details in the System information window, a real `pkexec` prompt for the
  slot details, package installation on Fedora and Debian/Ubuntu.
- *Disconnect* uses `umount`; without a matching `fstab` entry (`user`/`users` option) it reports a permission error.
- A network share mounted by IP but configured by host name is still not matched.
- `removeNetwork` only writes an empty password into KWallet; `kwallet-query` cannot delete entries.
- There is no automated test suite in the repository. The Python logic was tested with simulated
  `lsblk`/`udisksctl` output and the UI by hand on KDE Plasma (see the notes above for the QML check of the newest changes).
- Up/Down arrow keys assume the same number of columns in the disk and network grids.

## Suggested for the first release

- `APP_VERSION` is `'2.0.0-beta.8.2'` (DriveDeck is a new major version after Fenestra This PC 1.x). For the final release set
  `'2.0.0'` and tag `v2.0.0`.
- Keep the licence file `COPYING` (GPL-3.0) from upstream in the repository.
- Add this file as `CHANGELOG.md` and mention in the README that the project is a fork of
  `naykkalak/fenestra-ce-pc`.

- Development note: the changes in this fork were created with the help of AI assistants (Claude, Gemini) and tested by the maintainer.
