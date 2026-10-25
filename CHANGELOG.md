# Changelog – Fork of Fenestra "This PC" (`ce_pc_plasma.py`)

This fork is based on **Fenestra This PC 1.1** by [naykkalak](https://github.com/naykkalak/fenestra-ce-pc)
(GPL-3.0-or-later). All original copyright notices are kept. This file lists every change made in the fork,
as required by GPL-3.0 §5(a) (prominent notice of modifications).

The exact line counts are best taken from the GitHub diff against upstream. The program is still the single file `ce_pc_plasma.py`. `PyQt6.QtNetwork` is used when available (otherwise the
single-instance feature is skipped); **NumPy** is an optional dependency for the live I/O graph (without it the graph is
hidden and everything else works).

---

## Unreleased – 2026-10-25 (modern look and monitoring)

### New features

- **Live I/O graph per drive.** A small sparkline on every mounted drive card shows read (green) and write (yellow)
  throughput of the last 60 seconds; the tooltip shows the current values (▼ read, ▲ write). A background thread
  (`_ioLoop`) reads `/proc/diskstats` once per second, turns the counter differences into bytes per second with NumPy and
  smooths them (`glaetten`, triangular 5-point window, edge-corrected). The scale is at least 1 MB/s so idle noise
  does not look like load. Device paths such as `/dev/mapper/…` are resolved to their kernel name. The data is a
  separate property (`ioStats`) so the disk list is not rebuilt every second (see bug fix 3).
- **Configurable "almost full" warning.** A gear with the current value in the ribbon group *Show* opens a small
  popup (slider 30–99 %, quick buttons 50 / 70 / 80 / 90 %). From the chosen level on, the usage bar and the ring turn red and the
  card shows a badge such as "⚠ 90 %" with the tooltip "Almost full". The value is stored in
  `~/.config/fenestra/ce-pc-reglages.json` (default 80 %; removed by `uninstall.sh --purge`). German texts are included.

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

### Visual changes

- **Donut ring** instead of the pie chart in the *Properties* dialog (`QtQuick.Shapes`, GPU curve renderer): rounded
  ends, percentage in the centre, animated fill, smooth colour change at the warning level.
- **Slimmer, fully rounded usage bars** (10 px, no frame) that animate to the current value, also when a window opens.
- **Softer card hover:** rounded corners, fade in/out, light tint on hover, accent colour and a thin accent strip on
  the selected card; the icon grows slightly under the mouse (drives, network locations, printers).

### Notes

- New optional dependency: **NumPy** (imported inside the sampler thread, so start-up time is unaffected). `install.sh`
  prints a hint when it is missing.
- Checked with a small test harness that loads the QML and listens to the engine warnings (0 warnings), plus
  screenshots of the rendered window. The harness is not part of the repository.
- A search/filter across all cards was tried and removed again: it only searched inside this window and added little.

## 1.2.0 – 2026-10-25

## Bug fixes

| # | Problem in the original | Fix |
|---|---|---|
| 1 | On Btrfs systems `lsblk` reports only one of several mount points per device (e.g. a subvolume such as `/var/tmp`). Double-clicking "Local Disk" therefore opened `/var/tmp` instead of the user's files, and the system drive was not recognised as `/` (sorting, root icon, `CEPC_SANTE_TEST` health test). | `lsblk` is queried with `MOUNTPOINTS` (plural, falls back to `MOUNTPOINT` on old util-linux). If a device has several mount points, `/` wins, otherwise the first non-system one. The system drive keeps the mount point `/`; `/` and `/var/tmp` open the **current user's home** (`os.path.expanduser("~")`) via the new helper `chemin_affiche()`. Works for every user and needs no hard-coded path or device. |
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
  `fenestra-ce-pc-<uid>`). `CEPC_MULTI=1` allows several windows for testing.
- **QML development mode:** `python3 ce_pc_plasma.py --dump-qml > ce_pc_plasma.qml` writes the UI to a file;
  `CEPC_QML=ce_pc_plasma.qml python3 ce_pc_plasma.py` loads it from there. The default stays a single-file install.
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

- *Disconnect* uses `umount`; without a matching `fstab` entry (`user`/`users` option) it reports a permission error.
- A network share mounted by IP but configured by host name is still not matched.
- `removeNetwork` only writes an empty password into KWallet; `kwallet-query` cannot delete entries.
- There is no automated test suite in the repository. The Python logic was tested with simulated
  `lsblk`/`udisksctl` output and the UI by hand on KDE Plasma (see the notes above for the QML check of the newest changes).
- Up/Down arrow keys assume the same number of columns in the disk and network grids.

## Suggested for the first release

- Set `APP_VERSION` (e.g. `'1.2'`) and tag the release.
- Keep the licence file `COPYING` (GPL-3.0) from upstream in the repository.
- Add this file as `CHANGELOG.md` and mention in the README that the project is a fork of
  `naykkalak/fenestra-ce-pc`.
- Update `install.sh` so that it installs the new version of `ce_pc_plasma.py`.

- Development note: the changes in this fork were created with the help of AI assistants (Claude, Gemini) and tested by the maintainer.
