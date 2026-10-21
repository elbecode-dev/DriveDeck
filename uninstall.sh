#!/usr/bin/env bash
# Fenestra – This PC : removal for the current user.
# SPDX-License-Identifier: GPL-3.0-or-later
#   ./uninstall.sh          remove the program, its icons, languages, menu entry and desktop shortcut
#   ./uninstall.sh --purge  also remove its settings and caches (window size, sections, network list, printers, scanners, update check)
set -euo pipefail

DATA="$HOME/.local/share/fenestra"
rm -f "$HOME/.local/bin/ce_pc_plasma.py"
rm -rf "$DATA/ce-pc-icones" "$DATA/ce-pc-langues"
rm -f "$HOME/.local/share/applications/fenestra-ce-pc.desktop"
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
[ -n "$DESK" ] && [ "$DESK" != "$HOME" ] || DESK="$HOME/Desktop"
rm -f "$DESK/fenestra-ce-pc.desktop"
rmdir "$DATA" 2>/dev/null || true          # only if no other Fenestra component uses it

if [ "${1:-}" = "--purge" ]; then
    rm -f "$HOME"/.config/fenestra/ce-pc-*.json "$HOME"/.cache/fenestra/ce-pc-*
    rm -rf "$HOME/.local/share/icons/ce_pc_cache"
    rmdir "$HOME/.config/fenestra" "$HOME/.cache/fenestra" 2>/dev/null || true
    echo "Settings and caches removed."
fi
echo "\"This PC\" has been removed. Bookmarks it added to Dolphin's \"Remote\" section are left untouched."
