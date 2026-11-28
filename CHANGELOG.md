# Changelog – DriveDeck (fork of Fenestra "This PC")

DriveDeck is based on **Fenestra This PC 1.1** by [naykkalak](https://github.com/naykkalak/fenestra-ce-pc)
(GPL-3.0-or-later). All original copyright notices are kept. This file lists every change made in the fork,
as required by GPL-3.0 §5(a) (prominent notice of modifications).

The exact line counts are best taken from the GitHub diff against upstream. The program is still a single file, now called `drivedeck.py` (formerly `ce_pc_plasma.py`). `PyQt6.QtNetwork` is used when available (otherwise the
single-instance feature is skipped); **NumPy** is an optional dependency for the live I/O graph (without it the graph is
hidden and everything else works).

---

## Unreleased

### Changed
- **Glanceable hardware window.** The main cards of every hardware tab (overview, CPU & board, GPU & display, memory, storage & buses, sensors & fans) now lead with what matters:
  - **Hero header:** a 36 px device symbol on a glass tile, the product name itself as the title (16 px bold – "AMD Ryzen 9 5900X", "NVIDIA GeForce RTX 4080 SUPER", "MPG X570 GAMING PRO CARBON WIFI", "KDE Plasma 6.8.3", the NVMe drive), an accent glass badge right next to it (socket, chipset, PCI slot, session type) and a muted subline (vendor, architecture, family/model/stepping, subsystem, driver).
  - **KPI tiles:** 3–4 compact tiles under the header with the value in 14 px semi-bold tabular figures and the label in 11 px below, for example cores/threads, max. clock, L3 cache and frequency driver for the CPU; VRAM with type, max. GPU clock, power limit and PCIe link (with the current link when it is lower) for the GPU; BIOS version, BIOS date and boot mode for the board; capacity, PCIe link and driver for NVMe drives. A value that is just too long shrinks to 12 px before it is cut. In a narrow card the tiles wrap evenly (2 + 2, not 3 + 1).
  - **2-column details:** the remaining rows of a main card sit in two columns; a value that does not fit half a card gets both columns.
  - **Shortened strings:** long technical values are shown short, for example the NVIDIA kernel module as "620.73.04 · Open Kernel Module". The full string stays in the tooltip, in click-to-copy and in the exported report.
  - **Graphics APIs:** OpenGL, OpenGL ES and Vulkan are shown as accent tiles ("OpenGL 4.6.0", "OpenGL ES 3.2", "Vulkan 1.4.363") with the driver and the profile or device API below. They sit in one card with the display server ("Desktop & graphics APIs") next to the GPU.
  - **Displays:** every active screen is a tile with a monitor symbol, the resolution in large type, a "Preferred" badge when it runs at its native resolution, the monitor name and diagonal (read from its EDID), and the connector, refresh rate and scaling as pills. Refresh rate and scaling come from `kscreen-doctor -j` under Plasma; without it the window falls back to the DRM mode list.
  - **Sensors:** each card is titled with the product (CPU model, mainboard model, drive model, GPU) and has the chip or source as a badge ("k10temp", "nct6797", "NVMe", "nvidia-smi"). Small cards (up to four readings) show every reading as a tile with its session minimum and maximum; the mainboard card keeps its two columns.
  - **Overview:** processor, graphics card (now with VRAM and driver version), mainboard, memory (installed, in use, load) and system (distribution, kernel, architecture, session badges) use the same header and tiles.
- **Merged cards:** BIOS/UEFI is part of the mainboard card, L3 cache and the frequency driver are part of the processor card, and the memory controller is part of the memory card. In the CPU tab the processor sits next to the mainboard.
- Chassis types are shown by name ("Desktop" instead of "3").
- Click-to-copy, keyboard navigation (header, subline, tiles and rows in order), the global search (`Ctrl+F`) and the 1.5 px glass lines are unchanged. 28 new texts are translated into all 12 languages.

### Fixed
- **Footer of the hardware window at minimum width:** in German and other long languages the footer was wider than the window between 820 and about 1040 px, so the whole window content was pushed past the right edge. Below 1100 px the slot-details button now shows only its icon (with a tooltip), and the "Copied to clipboard" message may shrink.

## 2.4.0 – 2026-11-28

### Added
- **System information is now a resizable hardware inspector.** A separate window instead of a fixed dialog: minimum 820 × 580, starts at 1180 × 780, has the normal maximize button, and remembers its size and maximized state (`hw_window` in `settings.json`). From 960 px of content width the cards are arranged in two columns (each card goes into the shorter column).
- **New category "Sensors & fans":** every temperature and fan speed from `/sys/class/hwmon` (CPU, NVMe and SATA drives, memory modules, mainboard, liquid coolers …) and NVIDIA GPUs through `nvidia-smi`, read in a background thread every 2 s while the window is open, each with the minimum and maximum of the session. Unconnected probes (≤ 0 or ≥ 127 °C) and fan headers that never turned are left out; without any sensor the window explains how to load the drivers.
- **New category "Storage & buses":** NVMe/SATA/RAID controllers with their PCIe generation and lanes (and the maximum when the link is slower), the drives behind NVMe controllers, SATA link speeds, USB host controllers and every USB device with its negotiated speed (1.5/12/480 Mb/s, 5/10/20/40 Gb/s), USB version, port and vendor:product ID. This category is refreshed every time the window opens.
- **CPU socket without root:** derived from the mainboard chipset (AM4, AM5, LGA1851, LGA1700, LGA1200, LGA1151, LGA2066, sTRX4, sWRX8; form-factor suffixes such as "B650M" understood) or else from the CPU family and model, and labelled as derived. The exact value from SMBIOS still wins when it is available.
- **Fan control row on the mainboard card (read-only).** A *Fan control* row under the mainboard's temperatures and fans shows who controls the fans: "BIOS automatic", "fancontrol active" (`systemctl is-active fancontrol`, checked at most every 10 s) or, when another tool has set the PWM outputs to manual, "Manual · 45 %" with the average duty cycle. DriveDeck only reads `pwmN_enable` and `pwmN`; it never writes to the fans and needs no root rights for this. For your own fan curve, use `pwmconfig` and fancontrol.
- **Optional extras in `install.sh`.** At the end, only in an interactive terminal and unless `--no-extras` or `--no-deps` is given, the installer offers vnstat (install, `systemctl enable --now vnstat`, register the interface of the default route with `vnstat --add`) and lm_sensors (install, `sensors-detect --auto`), each with `[y/N]` – Enter means no. Package names for pacman, dnf, apt and zypper. fancontrol is never enabled; the installer only explains `pwmconfig` and `systemctl enable --now fancontrol` (and not at all when fancontrol already runs). `shellcheck` is now clean (one old unquoted variable in the PyQt6 diagnosis fixed).
- **Search (`Ctrl+F`) across all categories** with hit-count capsules next to the categories; if the current category has no hit, the window switches to the first one that has. **Click to copy:** a click on any row copies "label: value" (with a short "Copied to clipboard"); with the keyboard, the arrow keys choose a row and Enter or Ctrl+C copies it.

- **Network tab with the active connection and data usage.** *Active connection* (interface, status, link speed and duplex, IPv4 and IPv6 addresses, default gateways, DNS servers – behind systemd-resolved's stub the real ones –, MAC address; read without root through `/proc/net/route`, `ioctl` and `/proc/net/if_inet6`) sits next to its *Network adapter* (model, subsystem, driver, PCIe link). Below, *Data usage* as a full-width table with download, upload and total: right now (rate), this session (since boot), today, this week (from Monday) and this month. Each period comes from `vnstat --json` when vnstat is installed **and its database covers the whole period** (created before the period began) – a freshly installed vnstat would otherwise report only its first minutes; until then, and without vnstat, DriveDeck keeps its own counter in `~/.local/share/drivedeck/net_usage.json`: every minute (and every 2 s while the window is open, and at exit) it adds the growth of the kernel counters of all physical interfaces to the current day, recognises a reboot by `/proc/sys/kernel/random/boot_id` and a reset counter without a reboot, writes at most every 5 minutes and keeps 400 days. The card says which source it uses.

### Changed
- **Cards in pairs instead of masonry.** Cards stay in their logical order, two per row with exactly the same height (flush tops and bottoms); lists and tables (USB devices, data usage, module lists, memory modules, interfaces) and a card left over at the end span the full width. In wide cards the label column is at most 280 px.
- **Merged cards:** the temperature probes of the memory modules (jc42 …) are one *Memory* card ("Module 1", "Module 2"); SATA/RAID controllers and USB host controllers are one card each with a row per controller, NVMe controllers keep one card each with their drive first.
- **Sensor cards grouped by size:** CPU next to GPU, memory next to the liquid cooler, then the mainboard over the full width, then the drives in pairs – no small card is stretched next to a tall one any more. A card with more than six readings (the mainboard's Super-I/O chip) spans the full width and splits into two columns with small headings, *Temperatures* on the left and *Fans* on the right, with the fan control row across both.
- The cards of the hardware window are no longer rebuilt every 2 s: the repeaters count rows, cards and lines and read their data by index, so a sensor update changes only the bound values. Hover, tooltips and keyboard selection survive the update.
- Card titles are calm 13 px semi-bold in sentence case instead of letter-spaced capitals; the remaining English values are translated too ("preferred mode", "running …", "rank …", "version …", "used by …", "Secure Boot on/off", "Wi-Fi/Ethernet", "full/half duplex", "from the model name" – 37 new texts in all 13 languages), while the exported report stays English.
- The window uses the main window's style: category list with 13 px text, 18 px icons and the soft selection pill (no more violet box), 1.5 px glass lines under the header, between categories and content and above the footer, cards with radius 12, rows with radius 8, muted labels and tabular figures. Keyboard: Tab moves search → categories → content → buttons; `Esc` clears the search, then closes.
- **All card titles and labels are translated** (114 new texts in all 13 languages, including the short values "enabled", "none", "connected" …). The exported report keeps English labels and values.

### Fixed
- `qmllint` had silently stopped analysing the file after the first JavaScript callback inside the window (`map`/`filter`/`reduce` with a function) – the window uses plain loops, and the whole file is checked again.

## 2.3.1 – 2026-11-27

### Fixed
- **Header hairlines line up across all three columns.** The line under the sidebar header ("This PC · 16 items") sat at 68 px, the one under the inspector header ("Gaming-Rig") at 100 px, and with the compact toolbar the line under the toolbar added a third height (99 px). All three now sit on one shared header height (`topBarH`, 88 px × font scale) that is made of two bands: the title band (`titleBarH` = `topBarH` − `compactBarH`, 40 px: window title, settings and inspector buttons, window buttons) and a band as tall as the compact toolbar (48 px: sidebar header, compact toolbar, inspector header – all on one row). With the compact toolbar the lines join into one continuous line from the left to the right window edge; with the full ribbon the two side lines stay level and the ribbon keeps its own line.
- The window buttons in the inspector are centred on the window title; the inspector header (system overview and selected item) moved out of the scrolling area into the fixed header band, with a 40 px icon and a one-line title (the full name in a tooltip when it is cut).

### Changed
- **Stronger, glass-tinted dividers.** The column dividers and the header lines are now 2 px, the inner section lines (inspector, settings, ribbon groups, compact toolbar) 1.5 px, in a soft, slightly cool translucent tint instead of a neutral stroke: `rgba(0.80, 0.86, 0.96, 0.12)` on dark and `rgba(0.10, 0.14, 0.22, 0.11)` on light themes. The three header lines still end exactly on the shared header height.
- **Larger, easier-to-read sidebar.** Entries use 13 px text and 18 px icons in 34 px rows; the section headings ("Quick access", "This PC") are 11.5 px semi-bold. The sidebar is 248 px wide (was 240) so that "Lokaler Datenträger" and its size still fit in German, Russian, French, Dutch and Polish.
- **Section headers in the main area** (Folders, Devices and drives, Network locations, Printers and devices) are category headings again: 12 px semi-bold capitals with 0.8 letter spacing (muted white 72 % / black 62 %), a 12 px chevron that turns 90° when the section opens or closes, the count in an accent glass capsule (20 px, 16 % fill, 1 px rim, a soft blurred glow behind it that brightens on hover or focus; no glow with software rendering) and a 1.5 px glass rule that fades out to the right. Chevron, title and capsule form one button with a hover surface and focus ring: clicking anywhere on it folds the section (before only the small arrow did), Tab goes main area → section headers → sidebar, Space/Enter fold, Esc returns, and screen readers hear "Folders, 6". The count's colour is the accent mixed with white or black, so it stays at least 6 : 1 with any accent (measured with Breeze Dark, Breeze Light and a dark violet scheme).

## 2.3.0 – 2026-11-27

### Added
- **Settings dialog** (`Ctrl+,`, a 28 px gear next to the inspector toggle, and "…" in the compact toolbar). One compact, keyboard-friendly dialog (about 440 px, `Esc` closes it) with three groups: *Appearance* (application name, "Always use the compact toolbar", which sections are shown), *Warning threshold for free space* (slider 1–50 % with tabular figures and a live preview of the red bar and the warning capsule) and *Notifications*. All controls are in the Tab order and have screen-reader names; the header title lines up with the content.
- **Desktop notifications** (off by default): once per drive and session when a drive or mounted share falls below the warning threshold, or a drive reports a SMART warning or failure. Sent with `notify-send`, or directly to `org.freedesktop.Notifications` over D-Bus when `notify-send` is missing; *Send test notification* checks the path.

### Fixed
- **Network shares mounted by IP address are recognised under their saved host name** (and the other way round). Both sides are resolved with `getaddrinfo` in the background thread that builds the list, waiting at most one second and caching the result for five minutes (one minute after a failure); identical names need no lookup at all.
- **Disconnecting a share that is not set up for normal users** (no `user` option in `/etc/fstab`) now offers once to disconnect it as administrator (`pkexec umount`, only for a mount point that is currently a network file system) instead of showing only "permission denied". Cancelling the password prompt shows no error.
- **Removing a network location deletes its password from KWallet** (`org.kde.KWallet.removeEntry` over D-Bus, kwalletd6 or kwalletd5) instead of only blanking it; without KWallet on D-Bus it still blanks it as before.

### Changed
- The settings that were spread over the ribbon's warning-threshold popup, the compact toolbar's "…" menu and the *About* window now live only in the settings dialog. **Warning threshold…** in the ribbon opens the dialog at the slider; the *Show* boxes in the full ribbon and the "Always use the compact toolbar" switch in the toolbar's right-click menu stay as shortcuts.
- 17 new texts in all 13 languages; "Change name…" is no longer used.

### Removed
- The separate warning-threshold popup (`warnPopup`).

## 2.2.1 – 2026-11-27

### Added
- **Complete translations in all 13 languages.** The 180 texts added by the fork (SMART health, inspector, compact toolbar, hardware overview, messages, About window …) were only translated into German and showed in English everywhere else. They are now in every `locale/*/LC_MESSAGES/drivedeck.po` and the compiled `.mo` files: Spanish, French, Italian, Japanese, Dutch, Polish, Brazilian Portuguese, Russian, Turkish, Simplified and Traditional Chinese (AI-assisted, not yet reviewed by native speakers – corrections welcome). German moved from the built-in `EXTRA_DE` table into `de.po`, so all languages now use the same gettext files; the German output is unchanged for every text.
- **Installer: explains why PyQt6 cannot be loaded.** When PyQt6 is installed but `python3` cannot import it, `install.sh` now says why instead of only reporting it as missing: a `python3` that is not the system Python (conda, pyenv, venv), PyQt6 modules whose file names end in a suffix this Python does not load (for example `QtCore.cpython-312-abi3-x86_64-linux-gnu.so` instead of `QtCore.abi3.so`), or the import error itself. It suggests reinstalling PyQt6 from the distribution and, as a last resort, the symlink workaround. Thanks to **3Shadow3S** for tracking this down and sharing the workaround ([#3](https://github.com/elbecode-dev/DriveDeck/issues/3)).

### Changed
- **Toolbar buttons size themselves to a two-line label.** The width used to follow only the longest word, so long labels such as "Ajouter un emplacement réseau" (French), "Een netwerklocatie toevoegen" (Dutch) or "Добавить сетевое расположение" (Russian) needed three lines and were cut off. The width now follows the best split into two lines; short two-word titles ("À propos", "О программе") stay on one line when that is barely wider.
- Shorter Russian and Turkish "free of" texts on the drive cards, which were a few pixels too wide for the card.

### Removed
- The `EXTRA_DE` table in `drivedeck.py` (German now lives in `de.po`), nine of its entries that nothing used any more, and four entries in every `.po` file that the program no longer uses ("Location", "Open with Dolphin", "{n} item(s)", "The username is required to remember the password.").

**Updating:** run `bash install.sh` again – it copies the new translation files. Replacing only `drivedeck.py` would leave the old `.mo` files in place, and German would lose the fork's texts.

## 2.2.0 – 2026-11-27

### Changed
- **Calmer side columns in the style of macOS Finder.** The sidebar and the inspector are no longer floating glass panels with their own outline, light edge and inner cards. Each is now a full-height column, flush with the window corners, set apart from the middle only by one luminance step (`rgba(255,255,255,0.045)` dark, `rgba(0,0,0,0.03)` light) and a single 1 px hairline (10 % white / black, Apple's separator alpha). The title bar and ribbon run without a break at the top edge.
- **Sidebar:** 240 px wide (was 330); a strict 32 px row rhythm (no gap between rows, pills inset 1 px top and bottom); selection and hover pills with 8 px side margin and radius 6, no border (selection 18 % accent, 10 % when the sidebar is not the active zone; hover 7 %, 150 ms colour fade); all icons 16 × 16 (eject and pin too) with 8 px to the text, in their theme colours; section headings in sentence case, 11 px DemiBold in the tertiary text colour, on the same 16 px edge as the header and its hairline, with a 12 px disclosure chevron that appears on hover (or when collapsed); drives with a 2 px capacity line 4 px under the name and the size on the right (eject and pin take its place on hover); tree levels indent by 16 px, the vertical guide lines are gone. Drives that are not mounted (a click mounts them) keep a readable secondary label and only dim their icon. The header is a plain row (28 px app icon, 14 px name, neutral version capsule, 12 px status) above a hairline instead of a gradient card.
- **Inspector:** 300 px wide (was 330); one calm column with 16 px margins and hairlines between the sections instead of cards. Header with a 44 px icon, 15 px title and 12 px subtitle. Key/value pairs follow the Finder "Get Info" grid on a fixed 20 px row rhythm: labels right-aligned in a fixed column (12 px, secondary text colour, wrapping to two lines instead of being cut off), values left-aligned in 12 px with tabular figures. The live usage of mode A is one "Activity" section with four compact rows and 24 px sparklines. The *SMART health* section has its disclosure chevron before the title, and status badges (SMART, updates) are 20 px capsules in muted Apple system colours (green, orange, red) without an outline; in light themes their text is one step darker so it stays above 4.5 : 1 on the tint.
- **Design audit against the Apple HIG (macOS, Liquid Glass).**
  - *Contrast:* secondary text no longer uses `opacity` 0.5–0.6 but two colour steps that were measured on the rendered window: `textSecondary` (70 % dark / 72 % light) and `textTertiary` (62 % / 66 %). Every text label now reaches WCAG AA (4.5 : 1) in Breeze Light, Breeze Dark and dark custom schemes; before, 31–40 labels in Breeze Light and 15 in a dark violet scheme failed. Only disabled toolbar buttons stay below, as WCAG allows.
  - *One status palette:* Apple system colours everywhere (blue, green, orange, red, purple, teal; the accessible dark red `#ff6961`); the theme's negative/neutral colours, Material blue and the Tailwind cyan/magenta are gone. Read/write use system cyan and pink. Usage bars are flat (no gradient).
  - *One selection language:* hover is a neutral 7 % fill, selection is the accent at 18 % (10 % when the zone is inactive), pressed one step stronger, in the sidebar, on the cards and in the toolbar alike. The 3 px accent stripe on selected cards is gone.
  - *Focus:* keyboard focus is a 3 px accent ring outside the element (50 %), concentric with it (inner radius + 3), on toolbar buttons, the compact toolbar, the warning-threshold entry and the window buttons.
  - *Motion:* every state change fades with 150 ms OutCubic; toolbar hovers no longer pop in, and the chips no longer scale up on hover.
  - *Radii:* four steps – 4 (chips, bars), 6 (controls, sidebar pills), 8 (card hover, panel tiles, toolbar buttons), 12 (window, panel); tiles in the 12 px panel sit 4 px in with radius 8.
  - *Calm:* main-area section titles are sentence case 13 px DemiBold with a plain count, no accent pill and no rule, with 24 px above; the system-center panel is a neutral surface with a hairline instead of the violet–blue–cyan glow; temperature and "almost full" chips are borderless capsules; the I/O sparkline lost its neon glow and pulse; the light edge of the hover glass is drawn only in dark themes, where it is visible.
  - *Icons:* ⚠, ▲ and ▼ are symbolic theme icons; folder icons are 64 px (was 67); disclosure chevrons are 12 px everywhere.
  - *Ink:* printers that report pure RGB primaries (`#00FFFF`, `#FF00FF`, `#FFFF00` …) are shown in muted print tones; in light themes the ink bars have an inner hairline so yellow stays visible.
  - *Grid:* all margins, paddings and spacings in the sidebar, inspector, cards and toolbar are on the 4 px grid (no more 1, 3, 5, 7, 10, 14, 17 or 18 px values outside the hairline compensation).
- The middle column gains about 120 px, so the compact toolbar now takes over only below about 2175 px window width (with both side columns, German).

### Removed
- The cursor spotlight in the sidebar and the `GlassCard`, `SpecEdge`, `CardGlow` and `RoundedBar` components, which nothing uses any more.

## 2.1.0 – 2026-11-26

Five non-destructive ideas from the upstream comparison with Fenestra This PC 2.1.1, built on DriveDeck's own architecture (background threads, lazy menus, inspector, keyboard chain, screen-reader names), and SMART for NVMe drives in USB enclosures.

### Added
- **Compact toolbar (48 px).** When the fixed ribbon groups no longer fit into the middle column, the ribbon switches automatically to a centred toolbar with the same commands as icons (tooltip, screen-reader name, Tab chain, focus ring). *Show* (sections), the warning threshold and the toolbar choice are in a "…" menu built on first use. "Always use the compact toolbar" (in "…" or by right-clicking the toolbar) keeps it on wide windows too; the setting is saved. The width the ribbon needs is measured only while it is shown and applied after the current evaluation, so the switch cannot feed back into itself.
- **SMART health through udisks2, without a password.** NVMe: wear (percent used), spare and its limit, power-on hours, power cycles, unsafe shutdowns, data written and read, media errors, critical warnings, temperature, self-test result. SATA/ATA: failing flag, power-on time, power cycles, reallocated, pending and uncorrectable sectors, SSD life, temperature, self-test. Read in a background thread (`busctl`, at most once a minute per drive) and shown as a collapsible *SMART health* section in inspector mode B and in the Properties window, with a Good/Warning/Critical pill. Drives without udisks2 SMART data (USB enclosures) say so and keep the full `smartctl` report with its bridge fallbacks.
- **Live click mode.** A `QFileSystemWatcher` on `~/.config` and `kdeglobals` (KConfig replaces the file when saving) re-reads the single/double-click setting 300 ms after a change; only a changed `kdeglobals` triggers a read.

### Changed
- **New preview** (`preview.png`, English, version 2.1.0; the IP address is a placeholder).
- **Scanner duplicates merged by IP address or model.** The address comes from `ip=` (airscan), `http(s)://<address>` (eSCL) or `:net:<address>` (epson2 and others); the model is compared without its source list ("platen,adf") and "Series". The entry with a source list or an eSCL address wins, so the card reads "Epson WF-4830 (Flatbed & ADF)". Old duplicates in the scanner cache are merged on start. `epson2:net:` scanners count as network scanners.
- **Wi-Fi printers are debounced:** offline only after three failed checks in a row; in between the card keeps its last ink levels.
- **Ink names by partial match** ("photo black", "matte black", "light cyan", "light magenta", "black", "cyan", "magenta", "yellow", "gray"; "toner" is kept as a suffix), translated. **Low ink** is the printer's own `marker-low-levels` threshold or 10 % if it declares none; card pills, tooltip, inspector and dialog all use this one flag (2.0.1 used a fixed 15 % in the card).

### Fixed
- **SMART status of NVMe drives in USB enclosures.** For a USB disk DriveDeck tried `-d sat` first; a USB-to-NVMe bridge answers that with an empty ATA placeholder ("SMART support is: Unavailable – device lacks SMART capability" or "Unknown"), which was accepted as the result, so the report showed nothing useful. Now:
  - The bridge is identified from sysfs (USB vendor `0bda` Realtek → `-d sntrealtek`, `152d` JMicron → `-d sntjmicron`, `174c` ASMedia → `-d sntasmedia`) and its driver is tried first, then smartctl's own USB database (no `-d`), then `-d sat` for SATA enclosures, then the other NVMe bridge drivers and `-d nvme`.
  - "SMART support is: Unavailable / Unknown" and "device lacks SMART capability" count as a failed attempt and move on to the next driver.
  - smartctl runs with `LC_ALL=C`, so numbers have no locale thousands separators.
  - The values of a successful report (NVMe: wear, spare and limit, power-on hours, power cycles, unsafe shutdowns, data written/read, media errors, critical warning, temperature; SATA: reallocated/pending/uncorrectable sectors, hours, cycles, temperature, life, last self-test) also fill the *SMART health* section of the inspector and the Properties window, with "Read with smartctl at HH:MM". For such drives the inspector offers **Read SMART…** (one password prompt, no report window). A report is kept for 60 s, so opening it again or reading it from the inspector does not ask for the password again; a cancelled password prompt now stays silent.
  - NVMe media and data integrity errors are reported as their own reason ("Media errors reported") instead of "Bad sectors".
  Checked on a FIKWOT FN501Pro 1 TB behind a Realtek RTL9210 (`0bda:9210`): `-d sntrealtek` answers first with the full NVMe health log.
- The ribbon's horizontal scroll bar could stay visible when the ribbon was hidden: attaching it to the Flickable overrides its `visible` binding. It now sits in a wrapper item that alone decides.

## 2.0.1 – 2026-11-26

Default file manager and terminal, an inspector toggle, full-height side panels, more system details, and the fixes from a full end-to-end audit (see `audits.md`, section 5l).

### Fixed
- **Free space cut off next to the warning pill.** On a nearly full drive the card showed "109.9 GB free of …" beside "⚠ 88 %". The 340 px card never has room for both, so it now shows "109.9 GB free" (the pill already shows the fill level); the full text is in the tooltip and the screen-reader name. Same for network locations.
- **Compact telemetry in narrow windows** was cut off in the middle of a number ("▲ 40,…"). If the full line does not fit, the network part is left out instead.
- **Window buttons were read in English** by screen readers on a German system ("Minimize", "Close"), because the translation table only collects literal texts. Fixed.
- **File system tooltip in the Properties dialog never appeared** (it asked the layout instead of the label whether the text was cut off).
- **Numbers that still shifted while changing:** section counters, the warning-threshold slider, the percentage in the Properties pie chart, ink levels in the printer dialog and the temperature in the Properties dialog now use tabular figures as well.
- **Trash size used a different decimal separator** ("2,9 MB" next to "173.1 GB" when the interface language and the number format differ); all sizes now follow the interface language.
- **Ink warnings are consistent:** a cartridge is marked low below 15 % (as on the card and in the inspector) or at the printer's own threshold, whichever comes first. Common ink names from CUPS are translated ("Black ink" → "Schwarz").
- **Terminal detection also reads the system-wide default** (`/etc/xdg/kdeglobals`), with your own `kdeglobals` taking priority, as in KDE. DriveDeck never picks itself as the folder handler.
- **qmllint (Qt 6.12.1) errors:** duplicate ids in the drive, network and printer card delegates, block-scoped `var` declarations (44) and three multi-line string literals are fixed; the remaining notes are listed in `audits.md`.
- **"Open in terminal" uses your terminal.** DriveDeck always preferred Konsole. It now uses `xdg-terminal-exec` if installed, otherwise the KDE default (`kdeglobals` → `TerminalApplication` / `TerminalService`), then `$TERMINAL`, then the first of Konsole, kitty, Alacritty, foot and WezTerm. The folder is passed with the terminal's own option (`--directory`, `--working-directory`, `--workdir`, `--cwd` …) and as the process working directory. Menus and the inspector say "Open in Kitty" (or the detected terminal) with its icon; the system monitor and storage analysis tools that need a terminal start in it as well.
- **Folders open in your default file manager.** DriveDeck always started Dolphin, even when another file manager was set as the default for folders. It now reads the default for `inode/directory` from the XDG `mimeapps.list` files and starts that program for local folders; the menu entry says "Open with File Explorer" (or whichever program is set). Network addresses (smb://, sftp://) still go through Dolphin or `xdg-open`, which handle the login. Without any default, Dolphin is used as before, then `xdg-open`.

### Added
- **Inspector toggle (`Ctrl+I`)** at the right of the title bar (wide windows): hides or shows the right inspector. The tooltip shows the shortcut in your language ("Strg+I").
- **The ribbon is reachable with the keyboard.** Tab now goes main area → sidebar → ribbon buttons and *Show* boxes → inspector toggle → window buttons → main area (Shift+Tab backwards, Esc back to the main area). The focused button gets a clear outline, Enter or Space triggers it, and a button hidden in a scrolled ribbon slides into view.
- **Unmount in the inspector** for mounted internal drives (not for the system itself), as in the card menu.
- **More screen-reader names:** sidebar rows (heading or list item with size, "not mounted" and selection state), the pin button and the "+" button in the sidebar, the sidebar header card, and every key/value row of the inspector in both modes.

### Changed
- **Full-height side panels (macOS-style):** the sidebar and the inspector run from the top to the bottom edge of the window; the title, the ribbon and the main area form the middle column between them, on one continuous glass surface with a hairline under the ribbon. The sidebar header card carries the app icon and moves the window when dragged (double-click maximizes); the inspector has a small header with the window buttons. Without the inspector (Ctrl+I or below 1280 px) the window buttons sit at the right of the title bar, and a compact CPU/RAM/network line appears at its left whenever neither the inspector nor the ribbon shows telemetry.
- **Centred ribbon:** with the inspector visible, the four groups are centred in the middle column; "System center" is only as wide as its three buttons. The sidebar now has a fixed width (330 px at the default font size).

- **One "Open with …" label in every context menu.** Folder cards and sidebar rows now say "Open with File Explorer" (or whichever file manager is set) with its icon, like drive and network cards. Network addresses that open through Dolphin/KIO keep a plain "Open".
- **New preview** (`preview.png`, English, 2200 px wide, with the inspector). The IP address in it is a placeholder.
- **More system details in the inspector header:** CPU and GPU model with live temperature (CPU from `k10temp`/`zenpower`/`coretemp`, GPU from `amdgpu`/`nouveau`/Intel sensors or `nvidia-smi`), the active CPU scheduler (`sched_ext` name such as `scx_bpfland`, otherwise EEVDF/CFS), the local IPv4 address with the session type (Wayland/X11), and a package update pill ("Up to date" in green or "3 updates" in amber) from `checkupdates`, checked 10 s after start and every 2 hours in the background. Every value is optional: without NVIDIA, `sched_ext`, a sensor or `checkupdates` the line or pill is simply missing.

---

## 2.0.0 – 2026-11-26

First stable release of DriveDeck. On top of rc5 it adds a calmer "liquid glass" look and closes the last open accessibility gap.

### Added
- **Specular hover.** Folders, drives, network locations and printers float freely on the background. Only on hover or keyboard selection a faint glass surface fades in (150 ms), with a hairline light edge along the top only.
- **Mount status dot.** Drives show a small green dot when mounted and a muted grey one when not; the details of unmounted drives are slightly dimmed.
- **Ink level pills.** Four vertical glass pills (8 × 40 px) with a dark track; below 15 % the outline turns red and pulses softly (only while the window is visible). The tooltip lists every colour with its exact percentage; printers that report no individual levels show a dash with an explanatory tooltip.
- **Screen-reader support.** Drive, network and printer cards, folder cards, temperature chips, the live chips, the ink bars and the ribbon buttons carry roles and localized names (name, free space, temperature, status), so Orca can read them.
- **Floating glass inspector** on the right (from 1280 px window width). With nothing selected it shows a system overview (distribution logo, host, kernel, Plasma, uptime, install date) and four live cards (CPU, RAM, storage I/O, network) with 60-second sparklines in JetBrains Mono. When a folder, drive, network location, printer or device is selected it shows a large icon, name and status pill, macOS-style key/value details (file system, mount point, device, size, free, used, temperature, read/write rate; printers: status, connection, address and every ink level with a bar and percentage) and quick actions (open, mount, safely remove, analyze storage, properties, scan, settings). Below 1280 px the inspector is hidden and the ribbon shows system info and telemetry as before.

### Changed
- **Calmer toolbar:** with the inspector visible, the system info block and the telemetry chips leave the ribbon.
- **Sidebar header card** with a turquoise-blue glass gradient and a high-contrast version badge.
- **Section headings** end in a fine continuous hairline instead of a fading accent line.
- **Readable scanner names:** "Epson WF-4830 Series platen,adf" becomes "Epson WF-4830 (Flatbed & ADF)".
- **Uniform toolbar and light-scheme contrast:** the title bar and ribbon use one opacity (95 % with blur), so the wallpaper no longer shows through brighter on the right; glass panels, cards and count badges get stronger outlines and darker accent text in light schemes.
- **Floating glass sidebar.** The sidebar is now a rounded glass panel (14 px) that floats with a margin to the window edge instead of a hard divider, with a hairline glass outline and a very faint cursor spotlight (paused while the window is minimized). The status bar at the bottom is gone; the item count lives in the new header card at the top of the sidebar (icon, name with version pill, "This PC · 17 items").
- **New preview.** `preview.png` shows the 2.0.0 interface with the inspector.
- **Sidebar entries.** Section headings are quiet capitals with a chevron and no big icons; hover and selection pills have a hairline light edge; pin icons rest at 18 % and fade in on row hover. Drives show a slim 3 px capacity bar with their size in the measurement font and an eject button on hover for removable media; unmounted drives are listed dimmed (48 %) and cannot be opened or pinned.
- **Typography.** If installed, DriveDeck uses **Inter** for the interface and **JetBrains Mono** for live measurements (both OFL, nothing is bundled; otherwise the system font is used). Window title and section headers are DemiBold with fine tracking, card titles DemiBold, details regular in the system size. Inter is set a touch tighter (−0.12 px) and without hinting for smooth, macOS-like outlines. Temperatures, I/O rates, live CPU/RAM/storage/network values and uptime/kernel info use JetBrains Mono with tabular figures. A free-space text that is cut off on a crowded card now shows its full text as a tooltip.
- **Slim 4 px usage bars** with a fine track and a soft gradient: cool blue/cyan normally, amber from the warning threshold, coral shortly before full.
- **Tabular figures** (`tnum`) for temperatures, I/O rates, capacity text and live values, so digits never shift when they update.
- **Calmer toolbar.** Ribbon icons rest slightly muted and light up on hover; disabled actions stay clearly recognisable (42 %). The ribbon and title bar are more opaque with KWin blur, and the main area is slightly denser (86 % to 93 %), so windows behind it no longer show through small labels.

### Fixed
- **Sidebar drive rows:** the size next to the capacity bar can no longer overlap the bar or the row edge.
- **Window buttons reachable by keyboard.** Tab now cycles main area → sidebar → minimize, maximize, close → main area (Shift+Tab backwards, Esc returns). Before, the program's own Tab handling never let the focus reach the buttons, although rc4 claimed so.
- **Empty CD/DVD drive** showed the green "mounted" dot; it is grey now.
- **Light colour schemes were treated as dark.** The hidden helper that reads the Plasma colours got no colours from Kirigami (only an invisible item), so every light/dark decision used the dark variant. It is now a visible zero-size item.

---

## 2.0.0-rc5 – 2026-11-18 (Release candidate 5)

### Fixed
- **Live chips and I/O graph missing after start.** In rc4 the CPU/RAM/storage/network chips and the I/O graph stayed hidden until the window was maximized: at start the window reported "not visible" to the background loops, which then stayed paused. The window state is now passed on directly.

---

## 2.0.0-rc4 – 2026-11-14 (Release candidate 4)

### Added
- **Keyboard shortcuts.** `Ctrl+Q` quits, `F2` renames the program.
- **Accessibility.** The window buttons can be reached with Tab and operated with Enter or Space, show a focus ring and carry screen-reader names.

### Changed
- **Settings are saved in bundles.** The warning-threshold slider, section state and window size are written once, 300 ms after the last change (and at exit), instead of at every step.
- **Context menus are built on first use.** Faster start and fewer elements rebuilt with the drive list.
- **Colours follow the Plasma colour scheme.** Gauge, warning and health colours adapt to light and dark schemes for better contrast; "Storage" and "Network" in the live chips are translated.

### Fixed
- Pulsing animations stop while the window is minimized.
- A harmless "object has been deleted" message at exit is no longer printed.

---

## 2.0.0-rc3 – 2026-11-09 (Release candidate 3)

### Fixed
- **Lost saves.** Settings and window state were written through one shared temp file, so simultaneous writers made saves fail (908 of 2400 in a stress test). Each write now uses its own temp file under a lock; leftovers of a hard abort (`kill -9`) are cleaned up at the next start.
- **Rage-clicking.** Starting the same program twice within one second (file manager, terminal, …) is now ignored instead of spawning dozens of processes.
- **Hung mounts and SMART lookups.** The "already running" checks are now race-free, so two threads never pile up on the same dead mount or disk.
- **Trash scan.** The time limit now also applies while reading very large sub-folders.

### Performance
- `lpstat -v` is no longer run a second time in every printer cycle (about 11 fewer processes per minute).
- `xdg-user-dir` is queried once per folder type instead of twice at start.

---

## 2.0.0-rc2 – 2026-11-09 (Release candidate 2)

### Fixed

- **Renaming the launcher.** The custom name is now written to every DriveDeck launcher: the application menu entry and
  any `drivedeck*.desktop` on the desktop (the installer's shortcut is a separate copy that was never updated), including
  translated `Name[xx]=` lines that would otherwise override `Name=`. Runs are serialised, so renaming twice in quick
  succession ends in the last name instead of a random state; a run cut short by closing the program is repeated at the next
  start. `update-desktop-database` and `kbuildsycoca6` run afterwards. If DriveDeck is installed system-wide only, a user
  copy of the launcher is created instead of touching `/usr`.
- **Type safety.** Pyright errors went from 87 to 0. Qt calls that can return nothing (screen, clipboard, style hints,
  incoming connection, QML context) are now guarded. Reading SMART no longer ends a background thread with an error when no
  variant returned data (a message is shown instead), and the disk temperature loop no longer relies on a possibly unset
  variable.

## 2.0.0-rc1 – 2026-11-08 (Release candidate)

First release candidate for 2.0.0: no new features are planned before the final release, only fixes.

### Added

- **Custom application name.** Right-click the title bar or the "This PC" heading (or click the small pencil that appears
  when you hover the header, or use *About → Application name*) to give DriveDeck any name, e.g. "My Computer" or
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

The current list is kept in the README (*Known limitations*).
