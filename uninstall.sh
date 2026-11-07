#!/usr/bin/env bash
# DriveDeck : removal for the current user.
# SPDX-License-Identifier: GPL-3.0-or-later
#   ./uninstall.sh          remove the program, its icons, languages, menu entry and desktop shortcut
#   ./uninstall.sh --purge  also remove its settings and caches (window size, pinned folders, network list, printers, scanners, update check)
set -euo pipefail

PURGE=0
for arg in "$@"; do
    case "$arg" in
        --purge) PURGE=1 ;;
        -h|--help) echo "Usage: ./uninstall.sh [--purge]"; echo "  --purge  also remove settings and caches"; exit 0 ;;
        *) echo "Unknown option: $arg (see ./uninstall.sh --help)"; exit 1 ;;
    esac
done

DATA="$HOME/.local/share/drivedeck"
rm -f "$HOME/.local/bin/drivedeck.py"
rm -rf "$DATA/icons" "$DATA/locale" "$DATA/drivedeck.png"
find "$HOME/.local/share/icons/hicolor" -name drivedeck.png -delete 2>/dev/null || true
rm -f "$HOME/.local/share/applications/drivedeck.desktop"
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
[ -n "$DESK" ] && [ "$DESK" != "$HOME" ] || DESK="$HOME/Desktop"
rm -f "$DESK/drivedeck.desktop"
rmdir "$DATA" 2>/dev/null || true          # only if no other component uses them

if [ "$PURGE" = 1 ]; then
    rm -rf "$HOME/.config/drivedeck" "$HOME/.cache/drivedeck" "$HOME/.local/share/icons/drivedeck_cache"
    echo "Settings and caches removed."
fi
# let the menu forget the entry
command -v update-desktop-database >/dev/null && update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
echo "\"DriveDeck\" has been removed. Bookmarks it added to Dolphin's \"Remote\" section are left untouched."
