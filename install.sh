#!/usr/bin/env bash
# Fenestra – This PC : installation for the current user (no root needed).
# SPDX-License-Identifier: GPL-3.0-or-later
#   ./install.sh                   install, add a menu entry and a desktop shortcut
#   ./install.sh --no-desktop-icon install without the desktop shortcut
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"
DATA="$HOME/.local/share/fenestra"
APPS="$HOME/.local/share/applications"
DESKTOP_ICON=1
[ "${1:-}" = "--no-desktop-icon" ] && DESKTOP_ICON=0

for f in ce_pc_plasma.py icons locale; do
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
for pair in "udisksctl:CD/DVD mounting" "eject:ejecting media" "smartctl:disk health (smartmontools)" \
            "smbclient:network shares (Samba client)" "lpstat:printers (CUPS client)" \
            "ipptool:ink levels (CUPS IPP tools)" "avahi-browse:real printer status (Avahi tools)" \
            "kwallet-query:remembered network passwords" "dolphin:opening folders" "xdg-open:opening files" \
            "busctl:disk health warnings" "scanimage:scanners (SANE)" "skanpage:scanning from the scanner card"; do
    cmd="${pair%%:*}"; what="${pair#*:}"
    command -v "$cmd" >/dev/null || echo "  optional $cmd not found — $what will not be available"
done
[ "$missing" = 0 ] || { echo "Install the missing items above, then run ./install.sh again. Nothing was installed."; exit 1; }

echo "Installing…"
mkdir -p "$BIN" "$DATA" "$APPS"
install -m 755 "$SRC/ce_pc_plasma.py" "$BIN/ce_pc_plasma.py"
rm -rf "$DATA/ce-pc-icones" "$DATA/ce-pc-langues"
cp -r "$SRC/icons" "$DATA/ce-pc-icones"
cp -r "$SRC/locale" "$DATA/ce-pc-langues"

cat > "$APPS/fenestra-ce-pc.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=This PC
Name[de]=Dieser PC
Name[es]=Este equipo
Name[fr]=Ce PC
Name[it]=Questo PC
Name[ja]=PC
Name[nl]=Deze pc
Name[pl]=Ten komputer
Name[pt_BR]=Este Computador
Name[ru]=Этот компьютер
Name[tr]=Bu bilgisayar
Name[zh_CN]=此电脑
Name[zh_TW]=本機
Comment=Drives, network locations, printers and devices at a glance
Comment[fr]=Disques, emplacements réseau, imprimantes et périphériques en un coup d'œil
Exec=python3 "$BIN/ce_pc_plasma.py"
Icon=computer
Terminal=false
Categories=System;FileTools;
DESKTOP
chmod 644 "$APPS/fenestra-ce-pc.desktop"

if [ "$DESKTOP_ICON" = 1 ]; then
    DESK="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
    [ -n "$DESK" ] && [ "$DESK" != "$HOME" ] || DESK="$HOME/Desktop"
    mkdir -p "$DESK"
    install -m 755 "$APPS/fenestra-ce-pc.desktop" "$DESK/fenestra-ce-pc.desktop"
    echo "  desktop shortcut: $DESK/fenestra-ce-pc.desktop"
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

echo "Done. Open \"This PC\" from the application menu or the desktop shortcut."
echo "To update later: download the new version and run this script again (your settings are kept)."
