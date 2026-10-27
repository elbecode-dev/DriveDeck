#!/usr/bin/env bash
# DriveDeck : removal for the current user.
# SPDX-License-Identifier: GPL-3.0-or-later
#   ./uninstall.sh          remove the program, its icons, languages, menu entry and desktop shortcut
#   ./uninstall.sh --purge  also remove its settings and caches (window size, pinned folders, network list, printers, scanners, update check)
set -euo pipefail

DATA="$HOME/.local/share/drivedeck"
rm -f "$HOME/.local/bin/drivedeck.py"
rm -rf "$DATA/icons" "$DATA/locale" "$DATA/drivedeck.png"
find "$HOME/.local/share/icons/hicolor" -name drivedeck.png -delete 2>/dev/null || true
rm -f "$HOME/.local/share/applications/drivedeck.desktop"
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
[ -n "$DESK" ] && [ "$DESK" != "$HOME" ] || DESK="$HOME/Desktop"
rm -f "$DESK/drivedeck.desktop"
rmdir "$DATA" 2>/dev/null || true          # only if no other component uses them

if [ "${1:-}" = "--purge" ]; then
    rm -rf "$HOME/.config/drivedeck" "$HOME/.cache/drivedeck"
    echo "Settings and caches removed."
fi
echo "\"DriveDeck\" has been removed. Bookmarks it added to Dolphin's \"Remote\" section are left untouched."
