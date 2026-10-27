#!/usr/bin/env bash
# DriveDeck : installation for the current user. The program itself needs no root; installing missing system packages does
# (sudo is asked once, and only if you agree).
# SPDX-License-Identifier: GPL-3.0-or-later
#   ./install.sh                   install, add a menu entry and a desktop shortcut, offer to install missing packages
#   ./install.sh --no-desktop-icon install without the desktop shortcut
#   ./install.sh --no-deps         do not install system packages (only report what is missing)
#   ./install.sh --yes             install missing packages without asking
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"
DATA="$HOME/.local/share/drivedeck"
ICONS="$HOME/.local/share/icons"
APPS="$HOME/.local/share/applications"
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
[ -n "$DESK" ] && [ "$DESK" != "$HOME" ] || DESK="$HOME/Desktop"
DESKTOP_ICON=1
DEPS=1
ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        --no-desktop-icon) DESKTOP_ICON=0 ;;
        --no-deps)         DEPS=0 ;;
        --yes|-y)          ASSUME_YES=1 ;;
        -h|--help)
            echo "Usage: ./install.sh [--no-desktop-icon] [--no-deps] [--yes]"
            echo "  --no-desktop-icon  install without the desktop shortcut"
            echo "  --no-deps          do not install system packages (only report what is missing)"
            echo "  --yes, -y          install missing packages without asking"
            exit 0 ;;
        *) echo "Unknown option: $arg (see ./install.sh --help)"; exit 1 ;;
    esac
done

for f in drivedeck.py icons locale assets; do
    [ -e "$SRC/$f" ] || { echo "Error: $f not found next to install.sh. Nothing was installed."; exit 1; }
done

# ---- which package manager ---------------------------------------------------------------------------------------------
PM=""
if command -v pacman >/dev/null; then PM=pacman
elif command -v dnf >/dev/null; then PM=dnf
elif command -v apt-get >/dev/null; then PM=apt
fi

# One line per requirement : kind:target | what it is for | required (1) or optional (0) | pacman | dnf | apt packages
#   cmd:X  program X in PATH      py:M  Python module M      qml:P  QML module directory P (below the Qt QML import path)
REQS=(
"py:PyQt6.QtQml|PyQt6 with QtQml|1|python-pyqt6|python3-pyqt6|python3-pyqt6 python3-pyqt6.qtqml python3-pyqt6.qtquick"
"qml:org/kde/kirigami|Kirigami (user interface)|1|kirigami|kf6-kirigami|qml6-module-org-kde-kirigami"
"qml:org/kde/desktop|Plasma Qt Quick style (qqc2-desktop-style)|1|qqc2-desktop-style|kf6-qqc2-desktop-style|qml6-module-org-kde-qqc2desktopstyle"
"qml:QtQuick/Dialogs|Qt Quick dialogs|1|qt6-declarative|qt6-qtdeclarative|qml6-module-qtquick-dialogs qml6-module-qtquick-controls qml6-module-qtquick-layouts qml6-module-qtquick-shapes qml6-module-qtquick-templates qml6-module-qtquick-window"
"cmd:lsblk|listing drives|1|util-linux|util-linux|util-linux"
"cmd:udevadm|device information|1|systemd|systemd-udev|udev"
"cmd:udisksctl|mounting and safely removing drives|0|udisks2|udisks2|udisks2"
"cmd:eject|ejecting media|0|util-linux|util-linux|eject"
"cmd:smartctl|disk health (SMART)|0|smartmontools|smartmontools|smartmontools"
"cmd:busctl|disk health warnings|0|systemd|systemd|systemd"
"cmd:smbclient|network shares (Samba client)|0|smbclient|samba-client|smbclient"
"cmd:lpstat|printers (CUPS client)|0|cups|cups-client|cups-client"
"cmd:ipptool|printer ink levels (CUPS IPP tools)|0|cups|cups-ipptool|cups-ipp-utils"
"cmd:avahi-browse|real printer status (Avahi tools)|0|avahi|avahi-tools|avahi-utils"
"cmd:kwallet-query|remembered network passwords (KWallet)|0|kwallet|kf6-kwallet|libkf6wallet-bin"
"cmd:dolphin|opening folders|0|dolphin|dolphin|dolphin"
"cmd:xdg-open|opening files|0|xdg-utils|xdg-utils|xdg-utils"
"cmd:xdg-user-dir|finding the desktop folder|0|xdg-user-dirs|xdg-user-dirs|xdg-user-dirs"
"cmd:konsole|\"Open in terminal\" and the Terminal button|0|konsole|konsole|konsole"
"cmd:scanimage|scanners (SANE)|0|sane|sane-backends|sane-utils"
"cmd:skanpage|scanning from the scanner card|0|skanpage|skanpage|skanpage"
"cmd:plasma-systemmonitor|System monitor button|0|plasma-systemmonitor|plasma-systemmonitor|plasma-systemmonitor"
"cmd:filelight|Analyze storage button|0|filelight|filelight|filelight"
"cmd:systemsettings|System Settings button|0|systemsettings|plasma-systemsettings|systemsettings"
"cmd:lspci|System information window (PCI devices)|0|pciutils|pciutils|pciutils"
"cmd:lscpu|System information window (CPU)|0|util-linux|util-linux|util-linux"
"cmd:glxinfo|System information window (OpenGL)|0|mesa-utils|glx-utils|mesa-utils"
"cmd:vulkaninfo|System information window (Vulkan)|0|vulkan-tools|vulkan-tools|vulkan-tools"
"cmd:pactl|System information window (audio)|0|libpulse|pulseaudio-utils|pulseaudio-utils"
"cmd:dmidecode|RAM slots and CPU socket|0|dmidecode|dmidecode|dmidecode"
"cmd:pkexec|asking for the administrator password (Polkit)|0|polkit|polkit|pkexec"
"py:PyQt6.QtNetwork|only one window at a time|0|python-pyqt6|python3-pyqt6|python3-pyqt6 python3-pyqt6.qtnetwork"
"py:numpy|live read/write graph on the drive cards|0|python-numpy|python3-numpy|python3-numpy"
)

QML_DIR="$(python3 -c "from PyQt6.QtCore import QLibraryInfo as L; print(L.path(L.LibraryPath.QmlImportsPath))" 2>/dev/null || true)"

present() {   # present kind:target
    case "$1" in
        cmd:*) command -v "${1#cmd:}" >/dev/null ;;
        py:*)  python3 -c "import ${1#py:}" 2>/dev/null ;;
        qml:*) [ -n "$QML_DIR" ] && [ -d "$QML_DIR/${1#qml:}" ] ;;
    esac
}

echo "Checking requirements…"
missing_required=0
declare -a pkgs=()
for row in "${REQS[@]}"; do
    IFS='|' read -r check what required p_arch p_dnf p_apt <<<"$row"
    present "$check" && continue
    if [ "$required" = 1 ]; then
        echo "  MISSING  $what (required)"; missing_required=1
    else
        echo "  missing  $what"
    fi
    case "$PM" in
        pacman) list="$p_arch" ;;
        dnf)    list="$p_dnf" ;;
        apt)    list="$p_apt" ;;
        *)      list="" ;;
    esac
    for p in $list; do
        case " ${pkgs[*]:-} " in *" $p "*) ;; *) pkgs+=("$p") ;; esac
    done
done

ask() {   # ask "question" : yes with --yes, or when you answer Y or just press Enter ; no without a terminal
    [ "$ASSUME_YES" = 1 ] && return 0
    [ -t 0 ] || return 1
    local a; read -r -p "$1 [Y/n] " a || return 1
    case "${a:-y}" in [yY]*) return 0 ;; *) return 1 ;; esac
}

run_root() { if [ "$(id -u)" = 0 ]; then "$@"; else sudo "$@"; fi; }

install_packages() {
    case "$PM" in
        pacman) run_root pacman -S --needed --noconfirm "$@" ;;
        dnf)    run_root dnf install -y "$@" ;;
        apt)    run_root apt-get install -y "$@" ;;
    esac
}

if [ "${#pkgs[@]}" -gt 0 ] && [ "$DEPS" = 1 ]; then
    if [ -z "$PM" ]; then
        echo "  Your package manager is not supported by this script: install the items above with your distribution's tools."
    else
        echo
        echo "Missing packages ($PM): ${pkgs[*]}"
        if ask "Install them now (sudo asks for your password)?"; then
            # All at once; if one package name does not exist on this version of the distribution, retry one by one
            # so that the others still get installed.
            if ! install_packages "${pkgs[@]}"; then
                echo "  Some packages could not be installed together, trying them one by one…"
                for p in "${pkgs[@]}"; do install_packages "$p" >/dev/null 2>&1 || echo "  could not install $p"; done
            fi
        else
            echo "  Skipped. Install them later by running ./install.sh again (or ./install.sh --yes)."
        fi
        # check again : what is still missing?
        QML_DIR="$(python3 -c "from PyQt6.QtCore import QLibraryInfo as L; print(L.path(L.LibraryPath.QmlImportsPath))" 2>/dev/null || true)"
        missing_required=0
        for row in "${REQS[@]}"; do
            IFS='|' read -r check what required _ _ _ <<<"$row"
            [ "$required" = 1 ] && ! present "$check" && { echo "  MISSING  $what (required)"; missing_required=1; }
        done
    fi
fi
[ "$missing_required" = 0 ] || { echo "Install the required items above, then run ./install.sh again. Nothing was installed."; exit 1; }

# ---- services DriveDeck uses when they exist : printers (CUPS) and printer discovery (Avahi) ------------------------------
if [ "$DEPS" = 1 ] && [ -n "$PM" ] && command -v systemctl >/dev/null; then
    for pair in "cups.socket:lpstat" "avahi-daemon.service:avahi-browse"; do
        unit="${pair%%:*}"; tool="${pair#*:}"
        command -v "$tool" >/dev/null || continue
        systemctl list-unit-files "$unit" 2>/dev/null | grep -q "$unit" || continue
        systemctl is-enabled "$unit" >/dev/null 2>&1 && continue
        if ask "Enable $unit (needed to see printers)?"; then
            run_root systemctl enable --now "$unit" >/dev/null 2>&1 && echo "  enabled $unit" || echo "  could not enable $unit"
        fi
    done
fi

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
    mkdir -p "$DESK"
    install -m 755 "$APPS/drivedeck.desktop" "$DESK/drivedeck.desktop"
    echo "  desktop shortcut: $DESK/drivedeck.desktop"
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true   # let Plasma see the new menu entry and icon

echo "Done. Open \"DriveDeck\" from the application menu or the desktop shortcut."
echo "If DriveDeck is already running, close it first, otherwise the old version stays open."
echo "Tip: disk temperatures of SATA drives need the kernel module once:  sudo modprobe drivetemp"
echo "To update later: download the new version (or git pull) and run this script again (your settings are kept)."
