#!/usr/bin/env bash
# DriveDeck (community fork of Fenestra “This PC” by naykkalak) : installation for the current user (no root needed).
# SPDX-License-Identifier: GPL-3.0-or-later
#   ./install.sh                   install, add a menu entry and a desktop shortcut
#   ./install.sh --no-desktop-icon install without the desktop shortcut
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"
DATA="$HOME/.local/share/drivedeck"
ICONS="$HOME/.local/share/icons"
OLD_DATA="$HOME/.local/share/fenestra"
APPS="$HOME/.local/share/applications"
DESKTOP_ICON=1
[ "${1:-}" = "--no-desktop-icon" ] && DESKTOP_ICON=0

for f in drivedeck.py icons locale assets; do
    [ -e "$SRC/$f" ] || { echo "Error: $f not found next to install.sh. Nothing was installed."; exit 1; }
done

echo "Checking requirements…"
missing=0
if ! python3 -c "import PyQt6.QtCore, PyQt6.QtGui, PyQt6.QtQml, PyQt6.QtWidgets" 2>/dev/null; then
    echo "  MISSING  PyQt6 (with QtQml) — install your distribution's PyQt6 packages."
    missing=1
fi
for cmd in lsblk udevadm; do
    command -v "$cmd" >/dev/null || { echo "  MISSING  $cmd (required)"; missing=1; }
done
for pair in "udisksctl:mounting and safely removing drives" "eject:ejecting media" "smartctl:disk health (smartmontools)" \
            "smbclient:network shares (Samba client)" "lpstat:printers (CUPS client)" \
            "ipptool:ink levels (CUPS IPP tools)" "avahi-browse:real printer status (Avahi tools)" \
            "kwallet-query:remembered network passwords" "dolphin:opening folders" "xdg-open:opening files" \
            "busctl:disk health warnings" "scanimage:scanners (SANE)" "skanpage:scanning from the scanner card" \
            "konsole:\"Open in terminal\" in the right-click menu"; do
    cmd="${pair%%:*}"; what="${pair#*:}"
    command -v "$cmd" >/dev/null || echo "  optional $cmd not found — $what will not be available"
done
python3 -c "import PyQt6.QtNetwork" 2>/dev/null \
    || echo "  optional PyQt6.QtNetwork not found — a second start will open a second window instead of showing the first"
python3 -c "import numpy" 2>/dev/null \
    || echo "  optional NumPy not found — the live I/O graph on the drive cards stays hidden (install python-numpy)"
[ "$missing" = 0 ] || { echo "Install the missing items above, then run ./install.sh again. Nothing was installed."; exit 1; }

echo "Installing…"
mkdir -p "$BIN" "$DATA" "$APPS" "$ICONS/hicolor"
install -m 755 "$SRC/drivedeck.py" "$BIN/drivedeck.py"
rm -rf "$DATA/icons" "$DATA/locale"
cp -r "$SRC/icons" "$DATA/icons"
cp -r "$SRC/locale" "$DATA/locale"
install -m 644 "$SRC/assets/hicolor/256x256/apps/drivedeck.png" "$DATA/drivedeck.png"

# Application icon in every size, for the menu, the task bar and the window
cp -r "$SRC/assets/hicolor/." "$ICONS/hicolor/"
command -v gtk-update-icon-cache >/dev/null && [ -f "$ICONS/hicolor/index.theme" ] \
    && gtk-update-icon-cache -q -f -t "$ICONS/hicolor" 2>/dev/null || true

# Coming from "Fenestra This PC" / ce_pc_plasma.py : keep the old command working and remove the old entries
if [ -f "$BIN/ce_pc_plasma.py" ] && ! grep -q "DriveDeck forwarder" "$BIN/ce_pc_plasma.py" 2>/dev/null; then
    cat > "$BIN/ce_pc_plasma.py" <<'SHIM'
#!/usr/bin/env python3
# DriveDeck forwarder : the program used to be called ce_pc_plasma.py. This small file keeps old copies,
# shortcuts and commands working by starting drivedeck.py from the same folder.
import os
import runpy
import sys

ziel = os.path.join(os.path.dirname(os.path.realpath(__file__)), "drivedeck.py")
sys.argv[0] = ziel
runpy.run_path(ziel, run_name="__main__")
SHIM
    chmod 755 "$BIN/ce_pc_plasma.py"
    echo "  the old command ce_pc_plasma.py now starts DriveDeck"
fi
for old in "$APPS/fenestra-ce-pc.desktop"; do
    [ -f "$old" ] && rm -f "$old" && echo "  removed the old menu entry $(basename "$old")"
done
rm -rf "$OLD_DATA/ce-pc-icones" "$OLD_DATA/ce-pc-langues"
rmdir "$OLD_DATA" 2>/dev/null || true

cat > "$APPS/drivedeck.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=DriveDeck
Comment=Folders, drives, network locations, printers and devices at a glance
Comment[de]=Ordner, Laufwerke, Netzwerkorte, Drucker und Geräte auf einen Blick
Comment[fr]=Dossiers, disques, emplacements réseau, imprimantes et périphériques en un coup d'œil
Exec=python3 "$BIN/drivedeck.py"
Icon=drivedeck
Terminal=false
Categories=System;FileTools;
StartupWMClass=drivedeck
DESKTOP
chmod 644 "$APPS/drivedeck.desktop"

if [ "$DESKTOP_ICON" = 1 ]; then
    DESK="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
    [ -n "$DESK" ] && [ "$DESK" != "$HOME" ] || DESK="$HOME/Desktop"
    mkdir -p "$DESK"
    install -m 755 "$APPS/drivedeck.desktop" "$DESK/drivedeck.desktop"
    echo "  desktop shortcut: $DESK/drivedeck.desktop"
fi
# the old shortcut named "This PC" would still point to the old command : replace it, do not keep two
if [ -f "$DESK/fenestra-ce-pc.desktop" ]; then
    rm -f "$DESK/fenestra-ce-pc.desktop"
    echo "  removed the old desktop shortcut fenestra-ce-pc.desktop"
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true   # let Plasma see the new menu entry and icon

echo "Done. Open \"DriveDeck\" from the application menu or the desktop shortcut."
echo "If DriveDeck (or the old \"This PC\") is already running, close it first, otherwise the old version stays open."
echo "Your settings from the old version (~/.config/fenestra) are copied to ~/.config/drivedeck at the first start; the old files stay as a backup."
echo "To update later: download the new version (or git pull) and run this script again (your settings are kept)."
