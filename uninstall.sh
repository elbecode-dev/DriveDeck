#!/usr/bin/env bash
# DriveDeck : removal for the current user.
# SPDX-License-Identifier: GPL-3.0-or-later
#   ./uninstall.sh          remove the program, its icons, languages, menu entry and desktop shortcut
#   ./uninstall.sh --purge  also remove its settings and caches (window size, pinned folders, network list, printers, scanners, update check)
set -euo pipefail

DATA="$HOME/.local/share/drivedeck"
OLD_DATA="$HOME/.local/share/fenestra"
rm -f "$HOME/.local/bin/drivedeck.py" "$HOME/.local/bin/ce_pc_plasma.py"   # the second one: the forwarder (or an old install)
rm -rf "$DATA/icons" "$DATA/locale" "$DATA/drivedeck.png" "$OLD_DATA/ce-pc-icones" "$OLD_DATA/ce-pc-langues"
find "$HOME/.local/share/icons/hicolor" -name drivedeck.png -delete 2>/dev/null || true
rm -f "$HOME/.local/share/applications/drivedeck.desktop" "$HOME/.local/share/applications/fenestra-ce-pc.desktop"
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
[ -n "$DESK" ] && [ "$DESK" != "$HOME" ] || DESK="$HOME/Desktop"
rm -f "$DESK/drivedeck.desktop" "$DESK/fenestra-ce-pc.desktop"
rmdir "$DATA" "$OLD_DATA" 2>/dev/null || true          # only if no other component uses them

if [ "${1:-}" = "--purge" ]; then
    rm -rf "$HOME/.config/drivedeck" "$HOME/.cache/drivedeck"
    rm -f "$HOME"/.config/fenestra/ce-pc-*.json "$HOME"/.cache/fenestra/ce-pc-*   # settings of the old name
    rm -rf "$HOME/.local/share/icons/ce_pc_cache"
    rmdir "$HOME/.config/fenestra" "$HOME/.cache/fenestra" 2>/dev/null || true
    echo "Settings and caches removed."
fi
echo "\"DriveDeck\" has been removed. Bookmarks it added to Dolphin's \"Remote\" section are left untouched."
