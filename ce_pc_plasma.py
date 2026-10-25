#!/usr/bin/env python3
# Fenestra This PC (Custom Fork) — part of the Fenestra series
# Original Copyright (C) 2026 naykkalak
# Modifications and Btrfs/NVMe fixes Copyright (C) 2026 Christian
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ce PC (version Plasma/QML) - suit automatiquement les couleurs de Plasma."""

import configparser
import hashlib
import json
import re
import shutil
import socket
import os
import subprocess
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtWidgets import QApplication
try:
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
except ImportError:   # ohne QtNetwork läuft alles, nur ohne Einzelinstanz
    QLocalServer = QLocalSocket = None

# fenestraLangues : traductions au format gettext (un dossier par langue), l'anglais sert de repli
import gettext

LANG_DIR = os.path.expanduser("~/.local/share/fenestra/ce-pc-langues")
LANG_ALIAS = {"pt": "pt_BR", "pt_PT": "pt_BR", "zh": "zh_CN", "zh_SG": "zh_CN",
              "zh_HK": "zh_TW", "zh_MO": "zh_TW"}


def langues_systeme():
    """Langues du système, de la préférée à la suivante, arrêtées à la première variante d'anglais
    (l'anglais est la langue d'origine des textes : rien à traduire)."""
    brut = []
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        valeur = os.environ.get(var, "")
        if valeur:
            brut = [p.split(".")[0].split("@")[0] for p in valeur.split(":")]
            break
    if not brut:
        from PyQt6.QtCore import QLocale
        brut = [l.replace("-", "_") for l in QLocale().uiLanguages()]
    res = []
    for l in brut:
        if not l or l in ("C", "POSIX"):
            continue
        l = LANG_ALIAS.get(l, l)
        if l.split("_")[0] == "en":
            break
        if l not in res:
            res.append(l)
    return res


LANGUES = langues_systeme()
try:
    _TRAD = gettext.translation("ce-pc", LANG_DIR, languages=LANGUES, fallback=True) if LANGUES \
        else gettext.NullTranslations()
except Exception:
    _TRAD = gettext.NullTranslations()


# Neue Texte dieses Forks, die in den gettext-Dateien (.mo) nicht vorkommen : deutsche Übersetzung als Rückfall
EXTRA_DE = {
    "Mount": "Einbinden",
    "Open in terminal": "Im Terminal öffnen",
    "Copy path": "Pfad kopieren",
    "Disconnect": "Trennen",
    "Not mounted": "Nicht eingebunden",
    "Cannot mount": "Einbinden nicht möglich",
    "Cannot disconnect": "Trennen nicht möglich",
    "Cannot open terminal": "Terminal kann nicht geöffnet werden",
    "No terminal program found": "Kein Terminalprogramm gefunden",
    "Folder not found": "Ordner nicht gefunden",
    "Almost full": "Fast voll",
    "Open settings": "Einstellungen öffnen",
    "Quick access": "Schnellzugriff",
    "Temperature": "Temperatur",
    "Temperature:": "Temperatur:",
    "No subfolders": "Keine Unterordner",
    "Quick access ({n})": "Schnellzugriff ({n})",
    "Pin to Quick access": "An Schnellzugriff anheften",
    "Unpin from Quick access": "Von Schnellzugriff lösen",
    "Pin a folder…": "Ordner anheften…",
    "Move up": "Nach oben",
    "Move down": "Nach unten",
    "Drag folders here to pin them": "Ordner hierher ziehen, um sie anzuheften",
}


def tr(texte):
    """Texte traduit dans la langue du système ; le texte anglais si la langue n'est pas connue."""
    t = _TRAD.gettext(texte)
    if t == texte and LANGUES and LANGUES[0].split("_")[0] == "de":
        return EXTRA_DE.get(texte, texte)
    return t


def point_decimal():
    from PyQt6.QtCore import QLocale
    try:
        return QLocale(LANGUES[0]).decimalPoint() if LANGUES else "."
    except Exception:
        return "."


DECIMAL = point_decimal()


def table_traductions(qml):
    """Traductions de tous les textes passés à trad() dans le QML : {texte anglais: texte traduit}."""
    res = {}
    for m in re.finditer(r'trad\("((?:[^"\\]|\\.)*)"', qml):
        res[m.group(1)] = tr(m.group(1))
    return res


# (libellé, type xdg-user-dir, nom de repli, noms d'icônes à essayer)
USER_FOLDERS_SPEC = [
    ("Desktop", "DESKTOP", "Bureau",
     ["user-desktop", "folder-desktop", "folder"]),
    ("Documents", "DOCUMENTS", "Documents",
     ["folder-documents", "folder-text", "folder"]),
    ("Pictures", "PICTURES", "Images",
     ["folder-pictures", "folder-images", "folder"]),
    ("Music", "MUSIC", "Musique",
     ["folder-music", "folder-sound", "folder"]),
    ("Downloads", "DOWNLOAD", "Téléchargements",
     ["folder-downloads", "folder-download", "folder"]),
    ("Videos", "VIDEOS", "Vidéos",
     ["folder-videos", "folder-video", "folder"]),
]

ICON_CACHE_DIR = os.path.expanduser("~/.local/share/icons/ce_pc_cache")


def get_icon_theme_name():
    try:
        config = configparser.ConfigParser(strict=False)
        config.read(os.path.expanduser("~/.config/kdeglobals"))
        if "Icons" in config and "Theme" in config["Icons"]:
            return config["Icons"]["Theme"]
    except Exception:
        pass
    return "breeze"


def get_xdg_user_dir(xdg_type, fallback_name):
    try:
        out = subprocess.check_output(
            ["xdg-user-dir", xdg_type], stderr=subprocess.DEVNULL,
            text=True, timeout=3,
        ).strip()
        if out and os.path.isdir(out):
            return out
    except Exception:
        pass
    candidate = os.path.join(os.path.expanduser("~"), fallback_name)
    return candidate if os.path.isdir(candidate) else None


def list_user_folders():
    folders = []
    for label, xdg_type, fallback_name, icon_names in USER_FOLDERS_SPEC:
        path = get_xdg_user_dir(xdg_type, fallback_name)
        if not path:
            continue
        icon = next((n for n in icon_names if QIcon.hasThemeIcon(n)), "folder")
        folders.append({"label": tr(label), "path": path, "icon": icon})
    return folders


IGNORED_FSTYPES = {
    "tmpfs", "devtmpfs", "proc", "sysfs", "cgroup", "cgroup2",
    "efivarfs", "pstore", "securityfs", "debugfs", "tracefs",
    "configfs", "fusectl", "squashfs", "overlay", "autofs",
    "mqueue", "devpts", "binfmt_misc", "hugetlbfs", "bpf",
}
IGNORED_MOUNT_PREFIXES = (
    "/run/user", "/run/lock", "/run/credentials", "/run/systemd",
    "/sys", "/proc", "/dev", "/snap", "/boot", "/tmp",
)
# Pour les disques locaux, /var (sous-volumes Btrfs, conteneurs, Flatpak…) est ignoré en plus
DISK_IGNORED_PREFIXES = IGNORED_MOUNT_PREFIXES + ("/var",)


def ignore_mount(mountpoint, prefixes=IGNORED_MOUNT_PREFIXES):
    """True si le point de montage est (ou se trouve sous) un dossier système à ne pas afficher.
    Comparaison par dossier entier : « /bootdisk » n'est pas ignoré à cause de « /boot »."""
    return any(mountpoint == p or mountpoint.startswith(p + "/") for p in prefixes)


def taille(n_bytes):
    """Capacité lisible : Go avec une décimale sous 1 To, puis To avec trois chiffres significatifs."""
    g = n_bytes / (1024 ** 3)
    if round(g, 1) < 1024:
        return f"{g:.1f} {tr('GB')}".replace(".", DECIMAL)
    t = g / 1024
    dec = 2 if t < 10 else (1 if t < 100 else 0)
    return f"{t:.{dec}f} {tr('TB')}".replace(".", DECIMAL)


def nom_emplacement(loc):
    """Nom affiché d'un emplacement réseau : celui choisi par l'utilisateur, sinon « partage sur serveur »
    dans la langue du système (langueReseau)."""
    nom = (loc.get("name") or "").strip()
    if not nom or nom == "%s sur %s" % (loc["share"], loc["host"]):
        return tr("{share} on {host}").format(share=loc["share"], host=loc["host"])
    return nom


def get_base_disk_device(device):
    base = os.path.basename(device)
    m = re.match(r"^(sd[a-z]+|nvme\d+n\d+|mmcblk\d+)", base)
    return "/dev/" + m.group(1) if m else device


def _vrai(valeur):
    return str(valeur).strip().lower() in ("1", "true")


def _lsblk_json():
    """Sortie JSON de lsblk (un seul appel, TRAN et RM compris), ou None."""
    for colonne in ("MOUNTPOINTS", "MOUNTPOINT"):   # MOUNTPOINTS : util-linux 2.37 et plus récent
        try:
            out = subprocess.check_output(
                ["lsblk", "-J", "-b",
                 "-o", "NAME,PATH," + colonne + ",FSTYPE,SIZE,TYPE,LABEL,TRAN,RM"],
                stderr=subprocess.DEVNULL, text=True, timeout=5,
            )
            return json.loads(out)
        except Exception:
            continue
    return None


# Dateisysteme normaler Datenträger (Swap, LUKS, LVM, RAID usw. gehören nicht dazu)
DATA_FSTYPES = {"ext2", "ext3", "ext4", "btrfs", "xfs", "ntfs", "ntfs3", "exfat", "vfat", "f2fs", "jfs",
                "reiserfs", "udf", "hfsplus"}
PETITE_PARTITION = 1024 ** 3   # kleinere feste Partitionen (EFI, Recovery …) werden nicht angeboten


def partitions_non_montees(data):
    """[(label, périphérique, système de fichiers, taille, amovible, USB)] : volumes de données non montés,
    pour les proposer comme dans l'Explorateur Windows (clic = montage avec udisks)."""
    res = []

    def walk(devices, tran="", rm=False):
        for dev in devices:
            tran_dev = (dev.get("tran") or tran or "").lower()
            rm_dev = _vrai(dev["rm"]) if dev.get("rm") is not None else rm
            children = dev.get("children") or []
            if children:
                walk(children, tran_dev, rm_dev)
            path = dev.get("path") or (f"/dev/{dev['name']}" if dev.get("name") else "")
            fstype = (dev.get("fstype") or "").lower()
            if dev.get("type") not in ("part", "disk") or fstype not in DATA_FSTYPES \
                    or not path.startswith("/dev/"):
                continue
            if [m for m in (dev.get("mountpoints") or [dev.get("mountpoint")]) if m]:
                continue   # déjà monté (même sur un dossier système ignoré)
            try:
                taille_oct = int(dev.get("size") or 0)
            except (TypeError, ValueError):
                taille_oct = 0
            if taille_oct <= 0 or (not rm_dev and taille_oct < PETITE_PARTITION):
                continue
            res.append((dev.get("label") or "", path, fstype, taille_oct, rm_dev, tran_dev == "usb"))

    walk(data.get("blockdevices", []))
    return res


def list_real_disks_lsblk(data=None):
    """[(label, point de montage, périphérique, usage, système de fichiers, amovible, USB)].
    Un seul appel à lsblk (TRAN et RM compris), sans lecture de /sys ni appel par disque."""
    if data is None:
        data = _lsblk_json()
    if data is None:
        return []

    disks = []
    seen = set()

    def walk(devices, tran="", rm=False):
        for dev in devices:
            tran_dev = (dev.get("tran") or tran or "").lower()
            rm_dev = _vrai(dev["rm"]) if dev.get("rm") is not None else rm
            children = dev.get("children") or []
            if children:
                walk(children, tran_dev, rm_dev)

            path = dev.get("path") or (
                f"/dev/{dev['name']}" if dev.get("name") else None)
            if not path or not path.startswith("/dev/"):
                continue

            # Un périphérique peut avoir plusieurs points de montage (sous-volumes Btrfs…) :
            # « / » s'il y en a un, sinon le premier qui n'est pas un dossier système.
            mps = [m for m in (dev.get("mountpoints") or [dev.get("mountpoint")])
                   if m and m != "[SWAP]"]
            if "/" in mps:
                mountpoint = "/"
            else:
                mountpoint = next((m for m in mps if not ignore_mount(m, DISK_IGNORED_PREFIXES)), None)
            if not mountpoint or mountpoint in seen:
                continue

            fstype = dev.get("fstype") or ""
            if fstype in IGNORED_FSTYPES:
                continue

            try:
                usage = shutil.disk_usage(mountpoint)
            except (PermissionError, FileNotFoundError, OSError):
                continue

            if usage.total == 0:
                continue

            seen.add(mountpoint)
            disks.append((dev.get("label") or "", mountpoint, path, usage, fstype,
                          rm_dev, tran_dev == "usb"))

    walk(data.get("blockdevices", []))
    return disks


_ICONE_THEME = {}   # nom d'icône -> présent dans le thème ? (le thème ne change pas pendant l'exécution)


def disk_icon(names):
    for n in names:
        manual = os.path.join(ICON_CACHE_DIR, f"{n}.png")
        if os.path.isfile(manual):
            return "file://" + manual
    for n in names:
        if n not in _ICONE_THEME:
            _ICONE_THEME[n] = QIcon.hasThemeIcon(n)
        if _ICONE_THEME[n]:
            return n
    return names[-1]


def disque_present(path):
    """True si un disque est dans le lecteur optique (propriété udev ID_CDROM_MEDIA)."""
    try:
        out = subprocess.check_output(
            ["udevadm", "info", "--query=property", "--name=" + path],
            stderr=subprocess.DEVNULL, text=True, timeout=5)
        return any(l.strip() == "ID_CDROM_MEDIA=1" for l in out.splitlines())
    except Exception:
        return False


def lecteurs_optiques_sans_montage():
    """Lecteurs CD/DVD non montés (vides, ou avec un disque pas encore monté), pour les afficher quand même.
    Les lecteurs montés sont déjà dans la liste des disques."""   # lecteurOptique
    try:
        out = subprocess.check_output(
            ["lsblk", "-J", "-o", "NAME,PATH,TYPE,MOUNTPOINT,FSTYPE,LABEL"],
            stderr=subprocess.DEVNULL, text=True, timeout=5)
        data = json.loads(out)
    except Exception:
        return []
    res = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "rom" or dev.get("mountpoint"):
            continue
        path = dev.get("path") or ("/dev/" + (dev.get("name") or ""))
        if not path.startswith("/dev/"):
            continue
        present = disque_present(path) or bool(dev.get("fstype"))
        nom = dev.get("label") if (present and dev.get("label")) else tr("CD/DVD Drive")
        res.append({
            "rawLabel": nom, "label": nom, "mountpoint": "optical:" + path, "device": path,
            "fstype": dev.get("fstype") or "", "total": 0, "used": 0, "free": 0,
            "icon": disk_icon(["drive-optical", "media-optical-dvd", "media-optical"]),
            "isKey": False, "isUsb": False, "isOptical": True,
            "freeText": tr("Available") if present else tr("No disc"),
            "health": "", "healthText": "",
        })
    return res


# santeDisque (Ce PC 1.1) : état SMART surveillé par udisks2, lisible sans droits administrateur.
# Résultat : "" (bon ou inconnu), "warn" (signes d'usure), "fail" (disque défaillant).
# Pour essayer l'affichage : CEPC_SANTE_TEST=warn ou fail force l'état du disque système.
_SANTE = {}   # nom du périphérique (sda2, nvme0n1p2…) -> (instant de la lecture, état)
_UDISKS = "org.freedesktop.UDisks2"


def _udisks_prop(objet, interface, nom):
    try:
        r = subprocess.run(["busctl", "--system", "--json=short", "get-property", _UDISKS, objet, interface, nom],
                           capture_output=True, text=True, timeout=3)
        return json.loads(r.stdout).get("data") if r.returncode == 0 else None
    except Exception:
        return None


def disk_health(device, mountpoint=""):
    test = os.environ.get("CEPC_SANTE_TEST", "")
    if mountpoint == "/" and test in ("warn", "fail"):
        return test
    nom = os.path.basename(os.path.realpath(device))
    if not re.match(r"^[A-Za-z0-9_]+$", nom):
        return ""
    lu = _SANTE.get(nom)
    if lu and time.time() - lu[0] < 300:   # relu toutes les 5 minutes au plus (udisks2 ne l'actualise pas plus souvent)
        return lu[1]
    _SANTE[nom] = (time.time(), "")
    drive = _udisks_prop("/org/freedesktop/UDisks2/block_devices/" + nom, _UDISKS + ".Block", "Drive")
    if not drive or drive == "/":
        return ""
    etat = ""
    ata = _UDISKS + ".Drive.Ata"
    if _udisks_prop(drive, ata, "SmartSupported") and _udisks_prop(drive, ata, "SmartEnabled"):
        if _udisks_prop(drive, ata, "SmartFailing"):
            etat = "fail"
        elif (_udisks_prop(drive, ata, "SmartNumBadSectors") or 0) > 0 \
                or (_udisks_prop(drive, ata, "SmartNumAttributesFailing") or 0) > 0:
            etat = "warn"
    else:
        alertes = _udisks_prop(drive, _UDISKS + ".NVMe.Controller", "SmartCriticalWarning")
        if isinstance(alertes, list) and alertes:
            etat = "warn" if set(alertes) <= {"temperature"} else "fail"
    _SANTE[nom] = (time.time(), etat)
    return etat


HEALTH_TEXT = {"warn": "Signs of wear – see Properties", "fail": "Disk failing – back up your files"}


DISQUES_INTERVALLE = 10   # Sekunden zwischen zwei vollständigen Lesevorgängen (Füllstand)


def etat_montages():
    """Empreinte de /proc/self/mountinfo et /proc/partitions : change dès qu'un volume apparaît, disparaît
    ou est monté/démonté. None si illisible (on retombe alors sur une lecture régulière)."""
    try:
        with open("/proc/self/mountinfo", "rb") as f:
            a = f.read()
        with open("/proc/partitions", "rb") as f:
            b = f.read()
        return hash((a, b))
    except OSError:
        return None


def list_real_disks():
    result = []
    data = _lsblk_json()
    for label, mountpoint, device, usage, fstype, removable, usb in list_real_disks_lsblk(data):
        raw_label = label   # vide si le volume n'a pas de nom (sert de valeur de départ pour « Renommer »)
        optical = device.startswith("/dev/sr")
        if not label:   # disqueAmovible
            label = tr("Removable Disk") if (removable and not optical) else tr("Local Disk")
        if usb and not removable and not optical:
            label = "USB-" + label
        if optical:
            icon = disk_icon(["drive-optical", "media-optical-dvd", "media-optical"])
        elif removable:
            icon = disk_icon(["drive-removable-media"])
        elif mountpoint == "/":
            icon = disk_icon(["drive-harddisk-root", "drive-harddisk"])
        else:
            icon = disk_icon(["drive-harddisk"])
        result.append({
            "rawLabel": raw_label,
            "label": label, "mountpoint": mountpoint, "device": device,
            "fstype": fstype, "total": usage.total, "used": usage.used,
            "free": usage.free, "icon": icon, "isKey": removable,
            "isUsb": (removable or usb) and not optical,
            "isOptical": optical,
            "freeText": tr("{free} free of {total}").format(free=taille(usage.free), total=taille(usage.total)),
            "health": "" if optical else disk_health(device, mountpoint),
        })
        result[-1]["healthText"] = tr(HEALTH_TEXT[result[-1]["health"]]) if result[-1]["health"] else ""

    for label, device, fstype, taille_oct, removable, usb in (partitions_non_montees(data) if data else []):
        raw_label = label
        if not label:
            label = tr("Removable Disk") if removable else tr("Local Disk")
        if usb and not removable:
            label = "USB-" + label
        result.append({
            "rawLabel": raw_label, "label": label, "mountpoint": "unmounted:" + device, "device": device,
            "fstype": fstype, "total": taille_oct, "used": 0, "free": taille_oct,
            "icon": disk_icon(["drive-removable-media"] if removable else ["drive-harddisk"]),
            "isKey": removable, "isUsb": removable or usb, "isOptical": False, "isUnmounted": True,
            "freeText": tr("Not mounted") + " · " + taille(taille_oct),
            "health": "", "healthText": "",
        })

    def sort_key(d):
        if d["mountpoint"] == "/":
            return 0
        if d.get("isUnmounted"):
            return 3
        if d.get("isOptical"):
            return 1.5
        return 2 if d["isUsb"] else 1

    result.extend(lecteurs_optiques_sans_montage())
    result.sort(key=sort_key)
    return result


NETWORK_FSTYPES = {"cifs", "smb3", "smbfs", "nfs", "nfs4", "9p"}
NETWORK_FUSE_TYPES = {"fuse.sshfs", "fuse.davfs", "fuse.davfs2", "fuse.rclone"}


def _unescape_mount_path(path):
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), path)


def list_network_mounts():
    mounts = []
    seen = set()
    try:
        with open("/proc/mounts", "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return mounts
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        device, mountpoint, fstype = parts[0], parts[1], parts[2]
        device = _unescape_mount_path(device)   # « \\040 » = espace, aussi dans //serveur/Mon partage
        mountpoint = _unescape_mount_path(mountpoint)
        if fstype not in NETWORK_FSTYPES and fstype not in NETWORK_FUSE_TYPES:
            continue
        if mountpoint in seen:
            continue
        if ignore_mount(mountpoint):
            continue
        try:
            usage = shutil.disk_usage(mountpoint)
        except (PermissionError, FileNotFoundError, OSError):
            continue
        seen.add(mountpoint)
        label = os.path.basename(mountpoint.rstrip("/")) or device
        mounts.append({
            "label": label, "mountpoint": mountpoint, "device": device,
            "fstype": fstype, "total": usage.total, "used": usage.used,
            "free": usage.free,
            "icon": disk_icon(["folder-network", "network-server",
                               "network-workgroup", "folder-remote"]),
            "isKey": False, "isUsb": False, "isNetwork": True,
            "freeText": tr("{free} free of {total}").format(free=taille(usage.free), total=taille(usage.total)),
        })
    return mounts


CONFIG_DIR = os.path.expanduser("~/.config/fenestra")
NET_CONFIG = os.path.join(CONFIG_DIR, "ce-pc-reseau.json")


def load_net_locations():
    try:
        with open(NET_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        return [d for d in data if isinstance(d, dict) and d.get("host") and d.get("share")]
    except Exception:
        return []


def save_net_locations(locs):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = NET_CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(locs, f, ensure_ascii=False, indent=2)
    os.replace(tmp, NET_CONFIG)


def net_url(loc):
    from urllib.parse import quote
    user = (loc.get("user") or "").strip()
    return ("smb://" + (quote(user, safe="") + "@" if user else "")
            + loc["host"] + "/" + quote(loc["share"]))


PLACES = os.path.expanduser("~/.local/share/user-places.xbel")
PLACES_TAG = "fenestra-cepc-"


def _sync_places(locs):
    """Remet les favoris « Distant » de Dolphin en phase avec la liste des emplacements réseau de Ce PC.
    Ne touche qu'aux favoris créés par Ce PC (identifiant « fenestra-cepc-… »)."""
    try:
        with open(PLACES, encoding="utf-8") as f:
            texte = f.read()
    except OSError:
        return
    if "</xbel>" not in texte or "xmlns:bookmark=" not in texte:
        return
    from xml.sax.saxutils import escape

    def enlever(m):
        return "" if PLACES_TAG in m.group(0) else m.group(0)

    base = re.sub(r'[ \t]*<bookmark href="[^"]*">(?:(?!</bookmark>).)*</bookmark>[ \t]*\n?',
                  enlever, texte, flags=re.S)
    blocs = ""
    for loc in locs:
        url = net_url(loc)
        titre = nom_emplacement(loc)
        ident = PLACES_TAG + hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
        blocs += (' <bookmark href="' + escape(url, {'"': "&quot;"}) + '">\n'
                  '  <title>' + escape(titre) + '</title>\n'
                  '  <info>\n'
                  '   <metadata owner="http://freedesktop.org">\n'
                  '    <bookmark:icon name="folder-network"/>\n'
                  '   </metadata>\n'
                  '   <metadata owner="http://www.kde.org">\n'
                  '    <ID>' + ident + '</ID>\n'
                  '    <isSystemItem>false</isSystemItem>\n'
                  '   </metadata>\n'
                  '  </info>\n'
                  ' </bookmark>\n')
    debut, _, fin = base.rpartition("</xbel>")
    nouveau = debut + blocs + "</xbel>" + fin
    if nouveau == texte:
        return
    try:
        bak = PLACES + ".bak-fenestra"
        if not os.path.exists(bak):
            shutil.copy2(PLACES, bak)
        tmp = PLACES + ".fenestra.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(nouveau)
        os.replace(tmp, PLACES)
    except OSError as e:
        print("[ce_pc_plasma] favoris Dolphin :", e)


_PLACES_LOCK = threading.Lock()


def sync_places(locs):
    """Verrouillé : le thread de démarrage et un ajout/retrait ne partagent pas le même fichier temporaire."""
    with _PLACES_LOCK:
        _sync_places(locs)


WALLET_DOSSIER = "Fenestra Ce PC"
_ESPACE = {}          # url -> (heure, valeur ou None) : évite d'interroger le NAS toutes les 3 secondes
_PORTEFEUILLE = {"ko_jusqu": 0}


def wallet_cle(loc):
    return net_url(loc)


def wallet_ecrire(cle, mot_de_passe):
    """Range le secret dans KWallet (lu sur l'entrée standard : rien dans la ligne de commande)."""
    try:
        r = subprocess.run(["kwallet-query", "-f", WALLET_DOSSIER, "-w", cle, "kdewallet"],
                           input=mot_de_passe, text=True, capture_output=True, timeout=60)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _wallet_lire(cle):
    if time.time() < _PORTEFEUILLE["ko_jusqu"]:
        return None
    try:
        r = subprocess.run(["kwallet-query", "-f", WALLET_DOSSIER, "-r", cle, "kdewallet"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        _PORTEFEUILLE["ko_jusqu"] = time.time() + 300
        return None
    if r.returncode != 0:
        _PORTEFEUILLE["ko_jusqu"] = time.time() + 300
        return None
    secret = r.stdout.rstrip("\n")
    return secret or None


_WALLET_LOCK = threading.Lock()


def wallet_lire(cle):
    """Un seul accès à KWallet à la fois (les partages sont maintenant interrogés en parallèle)."""
    with _WALLET_LOCK:
        return _wallet_lire(cle)


def net_espace(loc):
    """(total, utilisé, libre) en octets d'un partage SMB, ou None. Mis en cache 2 minutes (5 en cas d'échec)."""
    url = net_url(loc)
    maintenant = time.time()
    if url in _ESPACE and maintenant < _ESPACE[url][0]:
        return _ESPACE[url][1]
    valeur = None
    mdp = wallet_lire(wallet_cle(loc)) if loc.get("user") else None
    if mdp:
        env = dict(os.environ)
        env["PASSWD"] = mdp
        try:
            r = subprocess.run(["smbclient", "//" + loc["host"] + "/" + loc["share"], "-U", loc["user"],
                                "-c", "ls"], env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=30)
            m = re.search(r"(\d+) blocks of size (\d+)\. (\d+) blocks available", r.stdout or "")
            if m:
                taille_bloc = int(m.group(2))
                total = int(m.group(1)) * taille_bloc
                libre = int(m.group(3)) * taille_bloc
                if total > 0:
                    valeur = (total, max(total - libre, 0), libre)
        except (OSError, subprocess.SubprocessError):
            valeur = None
        finally:
            env.pop("PASSWD", None)
    _ESPACE[url] = (maintenant + (120 if valeur else 300), valeur)
    return valeur


def _lire_texte(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def badge_health():
    """Pastilles de santé du disque (santeDisque) : orange = signes d'usure, rouge = défaillant. {état: adresse}."""
    res = {}
    for etat, couleur in (("warn", "#f7630c"), ("fail", "#c42b1c")):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">\n'
               '  <circle cx="10" cy="10" r="10" fill="%s"/>\n'
               '  <path d="M10 4.6 L10 11.4" stroke="#ffffff" stroke-width="2.6" stroke-linecap="round"/>\n'
               '  <circle cx="10" cy="15" r="1.5" fill="#ffffff"/>\n'
               '</svg>\n' % couleur)
        chemin = os.path.join(os.path.expanduser("~/.cache/fenestra"), "ce-pc-sante-%s.svg" % etat)
        try:
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            if not os.path.isfile(chemin) or _lire_texte(chemin) != svg:
                with open(chemin, "w", encoding="utf-8") as f:
                    f.write(svg)
            res[etat] = "file://" + chemin
        except OSError:
            res[etat] = ""
    return res


def badge_offline():
    """Crée (si besoin) l'image SVG de la pastille « non connecté » et renvoie son adresse file://."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">\n'
           '  <circle cx="10" cy="10" r="10" fill="#da4453"/>\n'
           '  <path d="M5.6 5.6 L14.4 14.4 M14.4 5.6 L5.6 14.4" stroke="#ffffff" stroke-width="2.6" '
           'stroke-linecap="round" fill="none"/>\n'
           '</svg>\n')
    chemin = os.path.join(os.path.expanduser("~/.cache/fenestra"), "ce-pc-pastille.svg")
    try:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        if not os.path.isfile(chemin) or _lire_texte(chemin) != svg:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(svg)
        return "file://" + chemin
    except OSError:
        return ""


SECT_CONFIG = os.path.join(CONFIG_DIR, "ce-pc-rubriques.json")   # rubriquesMemo (Ce PC 1.1)
SECTIONS = ("folders", "disks", "net", "printers", "quick")


def load_sections():
    """Rubriques : repliée ou non, affichée ou non. Par défaut, tout est affiché et déplié."""
    res = {k: {"collapsed": False, "shown": True} for k in SECTIONS}
    try:
        with open(SECT_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        for k in SECTIONS:
            d = data.get(k, {})
            res[k]["collapsed"] = bool(d.get("collapsed", False))
            res[k]["shown"] = bool(d.get("shown", True))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return res


# schnellzugriff : angeheftete Ordner der linken Leiste (wie « Schnellzugriff » im Windows-Explorer)
PINS_CONFIG = os.path.join(CONFIG_DIR, "ce-pc-epingles.json")
PIN_STANDARD = ("DESKTOP", "DOWNLOAD", "DOCUMENTS", "PICTURES")   # beim ersten Start angeheftet (Reihenfolge wie unter Windows)


def pin_normaliser(path):
    """Einheitlicher Schlüssel eines Ordners : derselbe Ordner wird nicht doppelt angeheftet.
    ~ wird expandiert, Endschrägstrich und « .. » entfallen. Symlinks werden bewusst NICHT aufgelöst : der Pin behält
    den Pfad, den man selbst gewählt hat (~/Schreibtisch bleibt ~/Schreibtisch), und ein Stick, der später unter einem
    anderen Pfad eingebunden wird, bleibt ein eigener Eintrag. Groß-/Kleinschreibung zählt (wie unter Linux)."""
    return os.path.abspath(os.path.expanduser(path))


def load_pins():
    """Angeheftete Ordner : [{path, label, icon}]. Fehlt die Datei (erster Start), sind Desktop, Dokumente,
    Downloads und Bilder angeheftet ; eine leere Liste bleibt leer."""
    try:
        with open(PINS_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        return [{"path": str(d["path"]), "label": str(d.get("label") or ""), "icon": str(d.get("icon") or "")}
                for d in data if isinstance(d, dict) and d.get("path")]
    except (OSError, ValueError, TypeError):
        pass
    name_zu_typ = {t: tr(l) for l, t, _, _ in USER_FOLDERS_SPEC}
    vorhanden = {f["label"]: f for f in list_user_folders()}
    return [{"path": vorhanden[name_zu_typ[t]]["path"], "label": name_zu_typ[t], "icon": vorhanden[name_zu_typ[t]]["icon"]}
            for t in PIN_STANDARD if name_zu_typ.get(t) in vorhanden]


def save_pins(pins):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = PINS_CONFIG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(pins, f, ensure_ascii=False)
        os.replace(tmp, PINS_CONFIG)
    except OSError as e:
        print("[ce_pc_plasma] schnellzugriff :", e)


def hat_unterordner(pfad, max_eintraege=5000):
    """Hat dieser Ordner mindestens einen (nicht versteckten) Unterordner? Bricht beim ersten Treffer ab.
    None = unbekannt (Ordner zu groß oder nicht lesbar zu klären) ; der Aufrufer zeigt dann vorsichtshalber den Pfeil."""
    gesehen = 0
    try:
        with os.scandir(pfad) as it:
            for e in it:
                gesehen += 1
                if gesehen > max_eintraege:
                    return None
                if e.name.startswith("."):
                    continue
                try:
                    if e.is_dir():
                        return True
                except OSError:
                    pass
    except PermissionError:
        return False
    except OSError:
        return None
    return False


def basis_platte(name):
    """Kernelname der ganzen Platte zu einem Blockgerät : Partition -> Platte, dm/LUKS/LVM -> darunterliegende Platte."""
    import glob
    for _ in range(8):
        slaves = glob.glob("/sys/class/block/%s/slaves/*" % name)
        if slaves:
            name = os.path.basename(slaves[0])
            continue
        pfad = os.path.realpath("/sys/class/block/" + name)
        if os.path.exists(os.path.join(pfad, "partition")):
            name = os.path.basename(os.path.dirname(pfad))
            continue
        break
    return name


_TEMP_UDISKS = {}   # Platte -> (Zeitpunkt, °C oder None) : udisks-Rückfall, höchstens einmal pro Minute


def platten_temperatur(platte):
    """Temperatur der ganzen Platte in °C oder None. Zuerst der Kernel-Sensor (hwmon : NVMe, SATA mit dem Modul
    drivetemp) – nur eine Datei lesen. Sonst udisks (SMART, in Kelvin) mit Zwischenspeicher."""
    import glob
    for datei in sorted(glob.glob("/sys/block/%s/device/hwmon*/temp1_input" % platte)):
        try:
            with open(datei) as f:
                return int(f.read().strip()) / 1000
        except (OSError, ValueError):
            continue
    lu = _TEMP_UDISKS.get(platte)
    if lu and time.time() - lu[0] < 60:
        return lu[1]
    wert = None
    drive = _udisks_prop("/org/freedesktop/UDisks2/block_devices/" + platte, _UDISKS + ".Block", "Drive")
    if drive and drive != "/":
        for iface, prop in ((_UDISKS + ".Drive.Ata", "SmartTemperature"), (_UDISKS + ".NVMe.Controller", "SmartTemperature")):
            kelvin = _udisks_prop(drive, iface, prop)
            if isinstance(kelvin, (int, float)) and kelvin > 0:
                wert = round(kelvin - 273.15, 1)
                break
    _TEMP_UDISKS[platte] = (time.time(), wert)
    return wert


def temperatur_stufe(platte, grad):
    """ok / warn / hot : Festplatten (drehend) vertragen weniger als SSDs und NVMe."""
    try:
        with open("/sys/block/%s/queue/rotational" % platte) as f:
            dreht = f.read().strip() == "1"
    except OSError:
        dreht = False
    warn, heiss = (45, 55) if dreht else (65, 75)
    return "hot" if grad >= heiss else ("warn" if grad >= warn else "ok")


def pin_infos(pins):
    """Für die Anzeige : Standard-Name und -Symbol ergänzen, 'exists' = Ordner gerade erreichbar (USB-Stick steckt?)."""
    res = []
    for p in pins:
        path = p["path"]
        res.append({"path": path, "label": p.get("label") or os.path.basename(path.rstrip("/")) or "/",
                    "icon": p.get("icon") or "folder", "exists": os.path.isdir(path)})
    return res


def chemin_affiche(path):
    """« / » (disque système) et /var/tmp (sous-volumes Btrfs) s'ouvrent sur le dossier personnel."""
    if path == "/" or path.startswith("/var/tmp"):
        return os.path.expanduser("~")
    return path


def lancer(cmd, cwd=None):
    """Lance un programme indépendant de Ce PC et récupère son code de sortie en arrière-plan
    (sans cela, chaque Dolphin fermé reste un processus zombie jusqu'à la fermeture de Ce PC)."""
    p = subprocess.Popen(cmd, cwd=cwd, start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    threading.Thread(target=p.wait, daemon=True).start()
    return p


def host_reachable(host, port=445, timeout=0.8):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def build_network_list():
    """Partages montés + emplacements ajoutés par l'utilisateur (avec leur disponibilité).
    Appelée dans un thread : un serveur qui ne répond pas ne doit pas figer la fenêtre.
    Les emplacements sont sondés en parallèle : un serveur éteint ne retarde pas les autres."""
    mounts = list_network_mounts()

    def entree(loc):
        key = ("//%s/%s" % (loc["host"], loc["share"])).lower()
        label = nom_emplacement(loc)
        url = net_url(loc)
        m = next((x for x in mounts if x["device"].lower().rstrip("/") == key), None)
        if m:
            entry = dict(m)
            entry.update({"label": label, "available": True, "mounted": True,
                          "configured": True, "url": url})
            return entry
        ok = host_reachable(loc["host"])
        esp = net_espace(loc) if (ok and loc.get("retenir")) else None
        return {
            "label": label, "mountpoint": url, "device": "//%s/%s" % (loc["host"], loc["share"]),
            "fstype": "smb", "total": esp[0] if esp else 0, "used": esp[1] if esp else 0,
            "free": esp[2] if esp else 0,
            "icon": disk_icon(["folder-network", "network-server",
                               "network-workgroup", "folder-remote"]),
            "isKey": False, "isUsb": False, "isNetwork": True,
            "freeText": (tr("{free} free of {total}").format(free=taille(esp[2]), total=taille(esp[0])) if esp
                         else (tr("Available") if ok else tr("Not connected"))),
            "available": ok, "mounted": False, "configured": True, "url": url,
        }

    locs = load_net_locations()
    result = []
    if locs:
        with ThreadPoolExecutor(max_workers=min(8, len(locs))) as pool:
            result = list(pool.map(entree, locs))
    used = {e["mountpoint"] for e in result if e["mounted"]}
    for m in mounts:
        if m["mountpoint"] not in used:
            entry = dict(m)
            entry.update({"available": True, "mounted": True, "configured": False,
                          "url": ""})
            result.append(entry)
    return result


DISK_CACHE = os.path.expanduser("~/.cache/fenestra/ce-pc-disques-cache.json")   # Laufwerke sofort beim Start anzeigen
NET_CACHE = os.path.expanduser("~/.cache/fenestra/ce-pc-reseau-cache.json")   # reseauCache


def charger_cache_reseau():
    """Dernier état connu des emplacements réseau, pour les afficher sans attendre (liste vide si absent)."""
    try:
        with open(NET_CACHE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(x, dict) for x in data):
            return data
    except (OSError, ValueError):
        pass
    return []


def charger_cache_disques():
    try:
        with open(DISK_CACHE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(x, dict) and "mountpoint" in x for x in data):
            return data
    except (OSError, ValueError):
        pass
    return []


_DISQUES_ECRIT = None


def enregistrer_cache_disques(liste):
    global _DISQUES_ECRIT
    try:
        contenu = json.dumps(liste)
        if contenu == _DISQUES_ECRIT:
            return
        os.makedirs(os.path.dirname(DISK_CACHE), exist_ok=True)
        tmp = DISK_CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(contenu)
        os.replace(tmp, DISK_CACHE)
        _DISQUES_ECRIT = contenu
    except (OSError, TypeError, ValueError):
        pass


_RESEAU_ECRIT = None   # cachesEcriture : dernier contenu écrit, pour ne réécrire que si la liste change


def enregistrer_cache_reseau(liste):
    global _RESEAU_ECRIT
    try:
        contenu = json.dumps(liste)
        if contenu == _RESEAU_ECRIT:
            return
        os.makedirs(os.path.dirname(NET_CACHE), exist_ok=True)
        tmp = NET_CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(contenu)
        os.replace(tmp, NET_CACHE)
        _RESEAU_ECRIT = contenu
    except (OSError, TypeError, ValueError):
        pass


PRN_CACHE = os.path.expanduser("~/.cache/fenestra/ce-pc-imprimantes-cache.json")   # imprimantesCache


def charger_cache_imprimantes():
    """Dernier état connu des imprimantes, pour les afficher sans attendre (liste vide si absent ou invalide)."""
    try:
        with open(PRN_CACHE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(x, dict) and "key" in x and "label" in x for x in data):
            return data
    except (OSError, ValueError):
        pass
    return []


_PRN_ECRIT = None   # cachesEcriture


def enregistrer_cache_imprimantes(liste):
    global _PRN_ECRIT
    try:
        contenu = json.dumps(liste)
        if contenu == _PRN_ECRIT:
            return
        os.makedirs(os.path.dirname(PRN_CACHE), exist_ok=True)
        tmp = PRN_CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(contenu)
        os.replace(tmp, PRN_CACHE)
        _PRN_ECRIT = contenu
    except (OSError, TypeError, ValueError):
        pass


IPPTOOL_TEST = "/usr/share/cups/ipptool/get-printer-attributes.test"   # imprimantesEncre


def libelle_connexion(uri):
    """Connexion lisible : « détectée automatiquement » pour une imprimante trouvée sur le réseau local."""
    if uri.startswith("implicitclass:") or "._ipp" in uri or "._print" in uri:
        return tr("Detected automatically on the network")
    if uri.startswith("usb:"):   # imprimantesUsb : sans le numéro de série
        return tr("Connected via USB")
    return uri


_ENCRE_CACHE = {}


def niveaux_encre(nom, cible=None):
    """Niveaux d'encre : d'abord ceux que CUPS connaît, sinon ceux que l'imprimante donne directement. Gardés 20 s."""   # encreDirecte
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", nom):
        return []
    memo = _ENCRE_CACHE.get(nom)
    if memo and time.time() - memo[0] < 20:
        return memo[1]
    res = _encre_url("ipp://localhost/printers/" + nom)
    if not res and cible and cible[1] == 631:
        res = _encre_url("ipp://%s:%d/ipp/print" % (cible[0], cible[1]))
    _ENCRE_CACHE[nom] = (time.time(), res)
    return res


def _encre_url(url):
    """Niveaux d'encre lus à cette adresse IPP : [{name, color, level, low}]. Liste vide si inconnus ou si ipptool est absent."""
    if not os.path.isfile(IPPTOOL_TEST):
        return []
    env = dict(os.environ, LC_ALL="C", LANG="C", LANGUAGE="C")
    try:
        out = subprocess.run(["ipptool", "-tv", url, IPPTOOL_TEST],
                             capture_output=True, text=True, timeout=5, env=env).stdout
    except Exception:
        return []

    def champ(cle):
        m = re.search(r"^\s*" + cle + r" \([^)]*\) = (.*)$", out, re.M)
        return [x.strip() for x in m.group(1).split(",")] if m else []

    noms, niveaux, couleurs = champ("marker-names"), champ("marker-levels"), champ("marker-colors")
    bas, types = champ("marker-low-levels"), champ("marker-types")
    res = []
    for i, n in enumerate(noms):
        try:
            niveau = int(niveaux[i])
        except (IndexError, ValueError):
            continue
        if niveau < 0 or niveau > 100 or (i < len(types) and "waste" in types[i]):
            continue
        try:
            seuil = int(bas[i])
        except (IndexError, ValueError):
            seuil = 0
        couleur = couleurs[i] if i < len(couleurs) and re.fullmatch(r"#[0-9A-Fa-f]{6}", couleurs[i]) else "#808080"
        res.append({"name": n, "color": couleur, "level": niveau, "low": niveau <= seuil})
    return res


PRN_CONNUES = os.path.expanduser("~/.config/fenestra/ce-pc-imprimantes.json")   # imprimantesConnues
_PRN_CONNUES_ECRIT = [None]
_PRN_ESSAI = {}


def charger_imprimantes_connues():
    """Imprimantes déjà vues : {nom de file: {label, device, default, addr, port}} (vide si absent ou invalide)."""
    try:
        with open(PRN_CONNUES, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
            return data
    except (OSError, ValueError):
        pass
    return {}


def enregistrer_imprimantes_connues(donnees):
    contenu = json.dumps(donnees, sort_keys=True)
    if contenu == _PRN_CONNUES_ECRIT[0]:
        return
    try:
        os.makedirs(os.path.dirname(PRN_CONNUES), exist_ok=True)
        tmp = PRN_CONNUES + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(contenu)
        os.replace(tmp, PRN_CONNUES)
        _PRN_CONNUES_ECRIT[0] = contenu
    except OSError:
        pass


def oublier_imprimante(nom):
    donnees = charger_imprimantes_connues()
    if nom in donnees:
        del donnees[nom]
        enregistrer_imprimantes_connues(donnees)


def cible_uri(uri):
    """(hôte, port) lu dans l'adresse d'une file réseau classique, sinon None (USB, file automatique, etc.)."""
    m = re.match(r"^(ipps?|https?|socket|lpd)://([^/:@]+)(?::(\d+))?", uri)
    if not m:
        return None
    defaut = {"ipp": 631, "ipps": 631, "http": 80, "https": 443, "socket": 9100, "lpd": 515}[m.group(1)]
    return m.group(2), int(m.group(3) or defaut)


def cle_service(uri):   # imprimantesDnssd
    """Nom d'annonce lu dans une adresse dnssd://… (sous la forme comparable), sinon None."""
    m = re.match(r"^dnssd://(.+?)\._(?:ipps?|printer)\._tcp\.local\.?/", uri)
    if not m:
        return None
    from urllib.parse import unquote
    return re.sub(r"[^A-Za-z0-9]+", "_", unquote(m.group(1)))


def adresse_avahi(nom, avait_adresse, cle=None):
    """(adresse IPv4, port) de l'imprimante annoncée sur le réseau sous ce nom de file, ou None.
    Au plus un essai toutes les 30 s (120 s si on connaissait déjà une adresse), car la recherche peut durer."""
    maintenant = time.time()
    if maintenant - _PRN_ESSAI.get(nom, 0) < (120 if avait_adresse else 30):
        return None
    _PRN_ESSAI[nom] = maintenant
    try:
        out = subprocess.run(["avahi-browse", "-rpt", "_ipp._tcp"], capture_output=True, text=True,
                             timeout=8).stdout
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
    except Exception:
        return None
    for ligne in out.splitlines():
        p = ligne.split(";")
        if len(p) < 9 or p[0] != "=" or p[2] != "IPv4":
            continue
        service = re.sub(r"\\(\d{3})", lambda m: chr(int(m.group(1))), p[3])
        if re.sub(r"[^A-Za-z0-9]+", "_", service) == (cle or nom):
            try:
                return p[7], int(p[8])
            except ValueError:
                continue
    return None


def imprimante_repond(adresse, port):
    try:
        with socket.create_connection((adresse, port), timeout=1.5):
            return True
    except OSError:
        return False


def list_printers():
    """Imprimantes CUPS : [{key, label, name, icon, statusText, device}]. Liste vide si aucune ou si CUPS est absent."""   # imprimantesInfo
    env = dict(os.environ, LC_ALL="C", LANG="C", LANGUAGE="C")
    try:
        out = subprocess.run(["lpstat", "-p", "-d", "-v"], capture_output=True, text=True,
                             timeout=5, env=env).stdout
    except Exception:
        return []
    defaut = ""
    uris = {}
    etats = {}
    ordre = []
    for ligne in out.splitlines():
        m = re.match(r"^system default destination: (\S+)", ligne)
        if m:
            defaut = m.group(1)
            continue
        m = re.match(r"^device for (\S+): (.*)$", ligne)
        if m:
            uris[m.group(1)] = re.sub(r"//[^/@]*@", "//", m.group(2).strip())
            continue
        m = re.match(r"^printer (\S+) (.*)$", ligne)
        if m:
            nom, reste = m.group(1), m.group(2)
            if "disabled" in reste:
                etat = tr("Offline")
            elif "now printing" in reste:
                etat = tr("Printing")
            else:
                etat = tr("Ready")
            etats[nom] = etat
            ordre.append(nom)
    connues = charger_imprimantes_connues()
    res = []
    vus = set(ordre)

    def sonde(nom):
        """Joignabilité et niveaux d'encre d'une imprimante (lent si elle est éteinte : un thread par file)."""
        uri = uris.get(nom, "")
        fiche = dict(connues.get(nom, {}))
        injoignable = False
        cible = None
        if not uri.startswith("usb:"):
            cible = cible_uri(uri)
            if cible is None and fiche.get("addr"):
                cible = (fiche["addr"], fiche.get("port", 631))
            ok = None
            if cible is not None:
                ok = imprimante_repond(*cible)
            if (ok is not True) and cible_uri(uri) is None:
                trouvee = adresse_avahi(nom, cible is not None, cle_service(uri))
                if trouvee:
                    cible = trouvee
                    ok = imprimante_repond(*cible)
            if cible is not None and cible_uri(uri) is None:
                fiche["addr"], fiche["port"] = cible
            injoignable = (cible is not None and ok is False)
        etat = tr("Offline") if injoignable else etats[nom]
        texte = etat + ((" · " + tr("Default")) if nom == defaut else "")
        peripherique = libelle_connexion(uri)
        fiche.update({"label": nom.replace("_", " "), "device": peripherique, "default": nom == defaut})
        carte = {"key": "printer:" + nom, "label": nom.replace("_", " "), "name": nom,
                 "icon": disk_icon(["printer"]), "statusText": texte,
                 "device": peripherique, "inks": [] if injoignable else niveaux_encre(nom, cible),
                 "offline": injoignable, "absent": False}
        return nom, fiche, carte

    if ordre:
        with ThreadPoolExecutor(max_workers=min(6, len(ordre))) as pool:
            for nom, fiche, carte in pool.map(sonde, ordre):
                connues[nom] = fiche
                res.append(carte)
    for nom, fiche in list(connues.items()):
        if nom in vus:
            continue
        texte = tr("Offline") + ((" · " + tr("Default")) if fiche.get("default") else "")
        res.append({"key": "printer:" + nom, "label": fiche.get("label") or nom.replace("_", " "), "name": nom,
                    "icon": disk_icon(["printer"]), "statusText": texte,
                    "device": fiche.get("device", ""), "inks": [], "offline": True, "absent": True})
    enregistrer_imprimantes_connues(connues)
    return res


_PERIPH_ETAT = [None, []]   # peripheriquesInfo : dernière liste lue (relue seulement si /proc/bus/input/devices change)
_PERIPH_TYPES = [("ID_INPUT_TOUCHPAD", "touchpad", "Touchpad", "input-touchpad"),
                 ("ID_INPUT_TABLET", "tablet", "Graphics tablet", "input-tablet"),
                 ("ID_INPUT_KEYBOARD", "keyboard", "Keyboard", "input-keyboard"),
                 ("ID_INPUT_MOUSE", "mouse", "Mouse", "input-mouse"),
                 ("ID_INPUT_JOYSTICK", "gamepad", "Game controller", "input-gaming")]
_PERIPH_ORDRE = {"keyboard": 0, "mouse": 1, "touchpad": 2, "tablet": 3, "gamepad": 4}


def list_peripheriques():
    """Claviers, souris, pavés tactiles, tablettes et manettes : mêmes champs que les imprimantes, plus indicator=True."""
    try:
        with open("/proc/bus/input/devices", encoding="utf-8", errors="replace") as f:
            signature = f.read()
    except OSError:
        return []
    if signature == _PERIPH_ETAT[0]:
        return _PERIPH_ETAT[1]
    try:
        out = subprocess.run(["udevadm", "info", "--export-db"], capture_output=True, text=True,
                             timeout=8).stdout
    except Exception:
        return []
    trouves = {}
    for bloc in out.split("\n\n"):
        lignes = bloc.splitlines()
        if not lignes or not re.match(r"^P: .*/input/input\d+$", lignes[0]):
            continue
        chemin = lignes[0][3:]
        if chemin.startswith("/devices/virtual/input/"):
            continue
        props = {}
        for ligne in lignes[1:]:
            if ligne.startswith("E: ") and "=" in ligne:
                cle, valeur = ligne[3:].split("=", 1)
                props[cle] = valeur.strip().strip('"')
        nom = props.get("NAME", "").strip()
        if not nom:
            continue
        if "/usb" in chemin:
            connexion = "USB"
        elif "/uhid/0005:" in chemin or "/bluetooth" in chemin:
            connexion = "Bluetooth"
        elif "/serio" in chemin or "/i8042" in chemin:
            connexion = tr("Built-in")
        else:
            connexion = ""
        m = re.search(r"(usb\d+/[\d.-]+)/", chemin)
        b = re.search(r"/uhid/(0005:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4})\.", chemin)
        groupe = m.group(1) if m else ("bt:" + b.group(1) if b else chemin)
        for propriete, genre, texte, icone in _PERIPH_TYPES:
            if props.get(propriete) == "1":
                cle = (groupe, genre)
                if cle not in trouves or len(nom) < len(trouves[cle]["name"]):
                    trouves[cle] = {"key": "device:" + chemin, "label": nom, "name": nom,
                                    "icon": disk_icon([icone]),
                                    "statusText": tr(texte) + ((" · " + connexion) if connexion else ""),
                                    "device": "", "inks": [], "indicator": True, "kind": genre, "_genre": genre}
                break
    # peripheriquesSouris : le « clavier » d'une souris (nom = nom de la souris + « Keyboard ») n'est pas un vrai clavier
    for (groupe, genre), d in list(trouves.items()):
        if genre == "keyboard" and any(g == groupe and gen == "mouse" and d["name"].startswith(s["name"])
                                       for (g, gen), s in trouves.items()):
            del trouves[(groupe, genre)]
    liste = sorted(trouves.values(), key=lambda d: (_PERIPH_ORDRE[d["_genre"]], d["label"]))
    for d in liste:
        del d["_genre"]
    _PERIPH_ETAT[0], _PERIPH_ETAT[1] = signature, liste
    return liste


# scannersInfo (Ce PC 1.1) : scanners trouvés par SANE (scanimage -L). La recherche réseau dure ~10 s :
# elle tourne en arrière-plan (au démarrage puis toutes les 10 minutes) et le dernier résultat est gardé
# en cache. Sécurité : un scanner RÉSEAU n'est affiché que s'il correspond à une imprimante installée
# sur ce PC (même nom de modèle) ; les scanners des autres sur le même Wi-Fi restent cachés.
SCAN_CACHE = os.path.expanduser("~/.cache/fenestra/ce-pc-scanners-cache.json")
_SCAN_TYPE = re.compile(r"\s+(?:(?:flatbed|platen|sheetfed|sheet-fed|adf|film|handheld)\s+)?scanner$"
                        r"|\s+multi-function peripheral$|\s+all-in-one$", re.I)


def _norme(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def detecter_scanners():
    """[{device, model, network}] d'après scanimage -L ; None si la recherche a échoué (on garde l'ancien résultat)."""
    if not shutil.which("scanimage"):
        return None   # absent : pas de série d'essais rapides, on garde l'ancien résultat
    try:
        out = subprocess.run(["scanimage", "-L"], capture_output=True, text=True, timeout=45).stdout
    except Exception:
        return None
    res, vus = [], set()
    for ligne in out.splitlines():
        m = re.search(r"device [`'](.+?)' is an? (.+)$", ligne.strip())   # la page HTML de certaines imprimantes peut précéder
        if not m:
            continue
        device, desc = m.group(1), m.group(2).strip()
        desc = re.sub(r"\s+ip=\S+$", "", re.sub(r"^(?:eSCL|WSD)\s+", "", desc))   # forme du pilote airscan
        backend = device.split(":", 1)[0].lower()
        if backend in ("v4l", "test", "pixma_test") or desc.lower().endswith("virtual device"):
            continue   # webcams et périphériques de test vus par SANE : pas des scanners
        model = _SCAN_TYPE.sub("", desc).strip() or desc
        if _norme(model) in vus:   # même scanner vu par deux pilotes (escl et airscan)
            continue
        vus.add(_norme(model))
        res.append({"device": device, "model": model,
                    "network": backend in ("escl", "airscan", "net") or "://" in device})
    return res


def charger_cache_scanners():
    try:
        with open(SCAN_CACHE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(x, dict) and "device" in x and "model" in x for x in data):
            return data
    except (OSError, ValueError):
        pass
    return []


def enregistrer_cache_scanners(liste):
    try:
        os.makedirs(os.path.dirname(SCAN_CACHE), exist_ok=True)
        tmp = SCAN_CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(liste, f)
        os.replace(tmp, SCAN_CACHE)
    except (OSError, TypeError, ValueError):
        pass


def cartes_scanners(scanners, trouves, imprimantes):
    """Cartes des scanners à afficher. scanners : dernière liste connue ; trouves : appareils vus à la
    dernière recherche (les autres sont « hors ligne ») ; imprimantes : cartes des imprimantes installées."""
    noms = {}   # nom comparable -> l'imprimante est-elle hors ligne ?
    for d in imprimantes:
        if d.get("indicator") or d.get("scanner"):
            continue
        for s in (d.get("name"), d.get("label")):
            if _norme(s):
                noms[_norme(s)] = bool(d.get("offline"))
    try:   # nom d'annonce réseau des files dnssd://… (« EPSON XP-540 Series »)
        out = subprocess.run(["lpstat", "-v"], capture_output=True, text=True, timeout=5,
                             env=dict(os.environ, LC_ALL="C", LANG="C", LANGUAGE="C")).stdout
        for m in re.finditer(r"^device for (\S+): dnssd://([^/]+?)\._(?:ipps?|printer)\._tcp", out, re.M):
            from urllib.parse import unquote
            hors = next((v for n, v in noms.items() if n == _norme(m.group(1))), False)
            noms[_norme(unquote(m.group(2)))] = hors
    except Exception:
        pass
    res = []
    for s in scanners:
        cle = _norme(s["model"])
        lies = [hors for n, hors in noms.items() if len(n) >= 6 and (cle in n or n in cle)]
        if s.get("network") and not lies:
            continue
        # scannerVeille : un scanner réseau suit l'état de son imprimante (relu toutes les 3 s), pas la recherche
        # de scanners (lente, toutes les 10 min) : imprimante éteinte = scanner « hors ligne » tout de suite,
        # imprimante en veille mais « Prête » = scanner affiché normalement
        if s.get("network") and lies:
            present = not all(lies)
        else:
            present = s["device"] in trouves
        texte = tr("Scanner") + " · " + (tr("Network") if s.get("network") else "USB")
        if not present:
            texte += " · " + tr("Offline")
        res.append({"key": "scanner:" + s["device"], "label": s["model"], "name": s["model"],
                    "icon": disk_icon(["scanner", "document-scan", "printer"]), "statusText": texte,
                    "device": "", "inks": [], "indicator": True, "scanner": True, "offline": not present})
    return res


# miseAJour (Ce PC 1.1) : au plus une fois par semaine, Ce PC demande à GitHub le numéro de la dernière
# version publiée. Rien n'est installé : un bandeau propose seulement d'ouvrir la page de la version.
# Aucune donnée personnelle n'est envoyée (GitHub voit l'adresse IP, comme pour toute visite).
# Désactivable dans « À propos ». Essai du bandeau : CEPC_MAJ_TEST=9.9 python3 ce_pc_plasma.py
MAJ_CONFIG = os.path.join(CONFIG_DIR, "ce-pc-mise-a-jour.json")
# Fork : leer = keine Update-Prüfung (das Original-Repository würde sonst ein Update melden, das diesen Fork
# überschreibt). Für ein eigenes Repository z. B.:
#   MAJ_API  = "https://api.github.com/repos/DEIN-NAME/DEIN-REPO/releases/latest"
#   MAJ_PAGE = "https://github.com/DEIN-NAME/DEIN-REPO/releases/latest"
MAJ_API = ""
MAJ_PAGE = ""
MAJ_INTERVALLE = 7 * 24 * 3600


def _version_tuple(v):
    """(1, 1) et (1, 1, 0) sont la même version : on complète par des zéros avant de comparer."""
    t = [int(x) for x in re.findall(r"\d+", v or "")[:4]]
    return tuple(t + [0] * (4 - len(t))) if t else ()


def charger_maj():
    etat = {"last": 0, "latest": "", "url": "", "enabled": True}
    try:
        with open(MAJ_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        etat["last"] = float(data.get("last", 0))
        etat["latest"] = str(data.get("latest", ""))
        etat["url"] = str(data.get("url", ""))
        etat["enabled"] = bool(data.get("enabled", True))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return etat


def enregistrer_maj(etat):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = MAJ_CONFIG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(etat, f)
        os.replace(tmp, MAJ_CONFIG)
    except OSError:
        pass


def lire_derniere_version():
    """(version, adresse de la page) de la dernière version publiée sur GitHub, ou None (hors ligne, erreur)."""
    import urllib.request
    try:
        req = urllib.request.Request(MAJ_API, headers={"User-Agent": "Fenestra-This-PC/" + APP_VERSION,
                                                       "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read(200000).decode("utf-8"))
        tag = str(data.get("tag_name", "")).lstrip("vV")
        url = str(data.get("html_url", ""))
        if not _version_tuple(tag) or not url.startswith("https://github.com/naykkalak/fenestra-ce-pc/"):
            return None
        return tag, url
    except Exception:
        return None


IO_FENSTER = 60   # ioVerlauf : Sekunden an Verlauf pro Laufwerk
SECTEUR = 512     # /proc/diskstats zählt immer in Sektoren zu 512 Bytes


def lire_diskstats():
    """{Kernelname: (gelesene Sektoren, geschriebene Sektoren)} aus /proc/diskstats."""
    stats = {}
    try:
        with open("/proc/diskstats") as f:
            for ligne in f:
                c = ligne.split()
                if len(c) >= 10:
                    stats[c[2]] = (int(c[5]), int(c[9]))
    except OSError:
        pass
    return stats


def nom_noyau(device):
    """/dev/mapper/xxx oder /dev/disk/by-… -> Name in /proc/diskstats (dm-0, nvme0n1p4, sdb1 …)."""
    return os.path.basename(os.path.realpath(device))


def glaetten(taux):
    """Glättet die Bytes/s-Reihe eines Laufwerks (1 Wert pro Sekunde, ältester zuerst) für die Sparkline.
    Rohwerte zucken stark, weil Schreibzugriffe stoßweise (Cache-Flush) kommen.
    Bekommt und liefert ein 1-D-NumPy-Array gleicher Länge."""
    import numpy as np
    kern = np.array([1.0, 2.0, 3.0, 2.0, 1.0])   # Dreiecksfenster : Spitzen bleiben Hügel, Zacken verschwinden
    if len(taux) < len(kern):
        return taux
    # Durch die tatsächliche Gewichtssumme teilen : an den Rändern (neuester Wert!) kein Abfall Richtung 0
    return np.convolve(taux, kern, "same") / np.convolve(np.ones(len(taux)), kern, "same")


class Backend(QObject):
    disksChanged = pyqtSignal()
    networksChanged = pyqtSignal()
    messageRequested = pyqtSignal(str, str)
    sharesFound = pyqtSignal(list)
    sharesError = pyqtSignal(str)
    smartReady = pyqtSignal(str, str)
    netUpdated = pyqtSignal(list)
    disksUpdated = pyqtSignal(list)
    printersUpdated = pyqtSignal(list)
    updateAvailable = pyqtSignal(str, str)   # miseAJour : (version, adresse de la page)
    printersChanged = pyqtSignal()
    ioChanged = pyqtSignal()
    pinsChanged = pyqtSignal()
    tempChanged = pyqtSignal()
    tempUpdated = pyqtSignal(dict)
    dirsListed = pyqtSignal(str, list)
    ioUpdated = pyqtSignal(dict)
    raiseRequested = pyqtSignal()   # ein zweiter Start soll das vorhandene Fenster nach vorn holen

    def __init__(self):
        super().__init__()
        self._disks = charger_cache_disques()   # sofort sichtbar, wird gleich vom Thread aktualisiert
        self._networks = charger_cache_reseau()
        self._printers = charger_cache_imprimantes()
        self.disksUpdated.connect(self._setDisks)
        self.netUpdated.connect(self._setNetworks)
        self.printersUpdated.connect(self._setPrinters)
        self._diskWake = threading.Event()
        self._netWake = threading.Event()
        self._prnWake = threading.Event()
        threading.Thread(target=lambda: sync_places(load_net_locations()), daemon=True).start()
        self._scanners = charger_cache_scanners()   # scannersInfo : dernière liste connue
        self._scanTrouves = {s["device"] for s in self._scanners}
        self._scanWake = threading.Event()
        threading.Thread(target=self._scanLoop, daemon=True).start()
        self._maj = charger_maj()
        threading.Thread(target=self._verifierMaj, daemon=True).start()
        threading.Thread(target=self._diskLoop, daemon=True).start()
        threading.Thread(target=self._netLoop, daemon=True).start()
        threading.Thread(target=self._printLoop, daemon=True).start()
        self._io = {}
        self.ioUpdated.connect(self._setIo)
        self._temps = {}
        self.tempUpdated.connect(self._setTemps)
        threading.Thread(target=self._tempLoop, daemon=True).start()
        self._pins = load_pins()
        self._pinInfos = pin_infos(self._pins)
        threading.Thread(target=self._ioLoop, daemon=True).start()

    @pyqtProperty("QVariantList", notify=disksChanged)
    def disks(self):
        return self._disks

    @pyqtProperty("QVariantMap", notify=tempChanged)
    def temps(self):
        return self._temps

    def _setTemps(self, neu):
        if neu != self._temps:
            self._temps = neu
            self.tempChanged.emit()

    def _tempLoop(self):
        # festplattenTemperatur : alle 5 s ; nur ein Signal, wenn sich ein (gerundeter) Wert oder eine Stufe ändert
        while True:
            res = {}
            for d in list(self._disks):
                if d.get("isOptical"):
                    continue
                try:
                    platte = basis_platte(os.path.basename(os.path.realpath(d["device"])))
                    grad = platten_temperatur(platte)
                except Exception:
                    grad = None
                if grad is not None:
                    res[d["device"]] = {"c": grad, "level": temperatur_stufe(platte, grad)}
            self.tempUpdated.emit(res)
            time.sleep(5)

    @pyqtProperty("QVariantList", notify=pinsChanged)
    def pins(self):
        return self._pinInfos

    def _refreshPins(self):
        neu = pin_infos(self._pins)
        if neu != self._pinInfos:
            self._pinInfos = neu
            self.pinsChanged.emit()

    def _setPins(self, pins):
        self._pins = pins
        save_pins(pins)
        self._refreshPins()

    @pyqtSlot(str, result=str)
    def displayPath(self, path):
        """Der Ordner, der sich beim Öffnen einer Karte tatsächlich öffnet (« / » -> persönlicher Ordner)."""
        return chemin_affiche(path)

    @pyqtSlot(str)
    def listDirs(self, path):
        """Unterordner von path im Hintergrund auflisten (Baum der Seitenleiste) ; Antwort kommt als dirsListed."""
        threading.Thread(target=self._listDirs, args=(path,), daemon=True).start()

    def _listDirs(self, path):
        namen = []
        try:
            with os.scandir(path) as it:
                for e in it:
                    if e.name.startswith("."):
                        continue
                    try:
                        if e.is_dir():
                            namen.append(e.name)
                    except OSError:
                        pass
        except OSError:
            pass
        namen.sort(key=str.casefold)
        # Für jedes Kind gleich prüfen, ob es selbst Unterordner hat : der Pfeil erscheint nur bei echten Unterordnern.
        # Zeitbudget, damit ein riesiger oder langsamer Ordner (Netzwerk) die Liste nicht aufhält ; Rest = unbekannt.
        ende = time.monotonic() + 2.0
        kinder = []
        for n in namen[:1000]:
            kind = os.path.join(path, n)
            kinder.append({"name": n, "path": kind,
                           "hasKids": hat_unterordner(kind) if time.monotonic() < ende else None})
        self.dirsListed.emit(path, [{**k, "hasKids": k["hasKids"] is not False} for k in kinder])

    @pyqtSlot(str, str, str)
    def pinPath(self, path, label, icon):
        """Ordner an den Schnellzugriff heften (auch file://-Adressen vom Ziehen aus Dolphin)."""
        if path.startswith("file://"):
            from urllib.parse import unquote, urlparse
            path = unquote(urlparse(path).path)
        if not path:
            return
        path = pin_normaliser(path)
        if not os.path.isdir(path) or any(pin_normaliser(p["path"]) == path for p in self._pins):
            return
        self._setPins(self._pins + [{"path": path, "label": label, "icon": icon}])

    @pyqtSlot(str)
    def unpinPath(self, path):
        key = pin_normaliser(path)
        self._setPins([p for p in self._pins if pin_normaliser(p["path"]) != key])

    @pyqtSlot(str, int)
    def movePin(self, path, delta):
        key = pin_normaliser(path)
        pins = list(self._pins)
        i = next((n for n, p in enumerate(pins) if pin_normaliser(p["path"]) == key), -1)
        j = i + delta
        if i < 0 or not 0 <= j < len(pins):
            return
        pins[i], pins[j] = pins[j], pins[i]
        self._setPins(pins)

    @pyqtProperty("QVariantMap", notify=ioChanged)
    def ioStats(self):
        return self._io

    def _setIo(self, new):
        self._io = new
        self.ioChanged.emit()

    def _ioLoop(self):
        # ioVerlauf : einmal pro Sekunde /proc/diskstats lesen, Raten per NumPy aus den Zählerdifferenzen bilden.
        # NumPy wird erst hier im Thread geladen : der Fensterstart bleibt davon unberührt.
        try:
            import numpy as np
        except ImportError:   # ohne NumPy : kein I/O-Verlauf, der Rest läuft normal
            return
        verlauf = {}   # Kernelname -> deque[(Zeitpunkt, gelesen, geschrieben)]
        while True:
            t = time.monotonic()
            for nom, (lu, ecrit) in lire_diskstats().items():
                verlauf.setdefault(nom, deque(maxlen=IO_FENSTER + 1)).append((t, lu, ecrit))
            resultat = {}
            for d in list(self._disks):
                h = verlauf.get(nom_noyau(d["device"]))
                if not h or len(h) < 2:
                    continue
                a = np.array(h, dtype=float)
                dt = np.diff(a[:, 0])
                taux = np.clip(np.diff(a[:, 1:], axis=0) * SECTEUR / dt[:, None], 0, None)   # Zähler-Reset -> 0
                resultat[d["device"]] = {
                    "read": glaetten(taux[:, 0]).tolist(), "write": glaetten(taux[:, 1]).tolist(),
                    "readRate": float(taux[-1, 0]), "writeRate": float(taux[-1, 1])}
            self.ioUpdated.emit(resultat)
            time.sleep(1)

    @pyqtProperty("QVariantList", notify=networksChanged)
    def networks(self):
        return self._networks

    @pyqtProperty("QVariantList", notify=printersChanged)
    def printers(self):
        return self._printers

    @staticmethod
    def _signature_disques(liste):
        """Ce qui est affiché : sans les octets exacts (used/free/total), qui bougent toutes les secondes sur le
        disque système sans changer le texte « x Go libres sur y Go ». Évite de reconstruire toutes les cartes
        (menu contextuel fermé, survol qui clignote) pour rien."""
        return [{k: v for k, v in d.items() if k not in ("used", "free", "total")} for d in liste]

    def _setDisks(self, new):
        if self._signature_disques(new) != self._signature_disques(self._disks):
            self._disks = new
            self.disksChanged.emit()
            self._refreshPins()   # ein Stick wurde ein-/ausgesteckt : Pins ausgrauen bzw. wieder aktivieren

    def _diskLoop(self):
        # lsblk, udevadm et busctl (santé SMART) bloquent : hors du fil de l'interface, comme le réseau.
        # Alle 1 s wird nur eine winzige Empreinte von /proc gelesen ; lsblk & Co. laufen erst bei einer Änderung
        # (Stick eingesteckt, Laufwerk ein-/ausgehängt) oder alle DISQUES_INTERVALLE s für die Füllstände.
        derniere, dernier = None, 0.0
        forcer = True
        while True:
            etat = etat_montages()
            delai = DISQUES_INTERVALLE if etat is not None else 3
            if forcer or etat != derniere or time.monotonic() - dernier >= delai:
                try:
                    liste = list_real_disks()
                    enregistrer_cache_disques(liste)
                    self.disksUpdated.emit(liste)
                except Exception as e:
                    print("[ce_pc_plasma] disques :", e)
                derniere, dernier = etat, time.monotonic()
            forcer = self._diskWake.wait(1)
            self._diskWake.clear()

    def _netLoop(self):
        # emplacements réseau seuls : un NAS éteint ne retarde plus la liste des imprimantes
        while True:
            try:
                liste = build_network_list()
                enregistrer_cache_reseau(liste)
                self.netUpdated.emit(liste)
            except Exception as e:
                print("[ce_pc_plasma] réseau :", e)
            self._netWake.wait(3)
            self._netWake.clear()

    def _printLoop(self):
        while True:
            try:
                imprimantes = list_printers()
                imprimantes = imprimantes + cartes_scanners(self._scanners, self._scanTrouves, imprimantes) \
                    + list_peripheriques()
                enregistrer_cache_imprimantes(imprimantes)
                self.printersUpdated.emit(imprimantes)
            except Exception as e:
                print("[ce_pc_plasma] imprimantes :", e)
            self._prnWake.wait(3)
            self._prnWake.clear()

    def _verifierMaj(self):
        # miseAJour : prévient d'une version plus récente (déjà connue, ou lue sur GitHub au plus une fois par semaine)
        if not MAJ_API:   # Fork ohne eigenes Repository : nichts prüfen
            return
        time.sleep(1.5)   # laisse la fenêtre s'afficher d'abord
        if not self._maj["enabled"]:   # case décochée dans « À propos » : ni vérification ni bandeau (essai compris)
            return
        test = os.environ.get("CEPC_MAJ_TEST", "")
        if test:
            self.updateAvailable.emit(test, MAJ_PAGE)
            return
        if time.time() - self._maj["last"] >= MAJ_INTERVALLE:
            lu = lire_derniere_version()
            if lu:
                self._maj.update({"last": time.time(), "latest": lu[0], "url": lu[1]})
                enregistrer_maj(self._maj)
        if _version_tuple(self._maj["latest"]) > _version_tuple(APP_VERSION):
            self.updateAvailable.emit(self._maj["latest"], self._maj["url"] or MAJ_PAGE)

    @pyqtProperty(bool, constant=True)
    def updateCheck(self):
        return self._maj["enabled"] and bool(MAJ_API)

    @pyqtProperty(bool, constant=True)
    def updateSupported(self):
        return bool(MAJ_API)

    @pyqtSlot(bool)
    def setUpdateCheck(self, actif):
        self._maj["enabled"] = bool(actif)
        enregistrer_maj(self._maj)

    def _scanLoop(self):
        # scannersInfo : recherche lente (~10 s), au démarrage puis toutes les 10 minutes ou sur « Actualiser ».
        # scannerVeille : une imprimante en veille ne répond pas toujours ; tant qu'une imprimante est
        # installée et qu'aucun scanner n'a répondu, on réessaie chaque minute (10 fois au plus).
        essais_rapides = 0
        while True:
            delai = 600
            try:
                trouves = detecter_scanners()
                imprimante = any(not d.get("indicator") and not d.get("scanner") for d in self._printers)
                if trouves == [] and imprimante and essais_rapides < 10:
                    essais_rapides += 1
                    delai = 60
                elif trouves:
                    essais_rapides = 0
                if trouves is not None:
                    # rangés par modèle : un scanner réseau qui change d'adresse (DHCP) ne fait pas de doublon
                    connus = {_norme(s["model"]): s for s in self._scanners}
                    for s in trouves:
                        connus[_norme(s["model"])] = s
                    vus = {s["device"] for s in trouves}
                    # un scanner disparu reste affiché « hors ligne », comme une imprimante éteinte
                    self._scanners = [s for s in connus.values() if s["device"] in vus or s.get("network")]
                    self._scanTrouves = vus
                    enregistrer_cache_scanners(self._scanners)
                    self._prnWake.set()
            except Exception as e:
                print("[ce_pc_plasma] scanners :", e)
            if self._scanWake.wait(delai):
                essais_rapides = 0   # « Actualiser » : on repart pour une série d'essais rapides
            self._scanWake.clear()

    def _setNetworks(self, new_net):
        if new_net != self._networks:
            self._networks = new_net
            self.networksChanged.emit()

    def _setPrinters(self, new_list):
        if new_list != self._printers:
            self._printers = new_list
            self.printersChanged.emit()

    @pyqtSlot(str)
    def forgetPrinter(self, name):   # imprimantesConnues
        oublier_imprimante(name)
        self._prnWake.set()

    @pyqtSlot(str)
    def saveSections(self, texte):
        try:
            data = json.loads(texte)
            etat = {k: {"collapsed": bool(data[k]["collapsed"]), "shown": bool(data[k]["shown"])}
                    for k in SECTIONS}
            os.makedirs(CONFIG_DIR, exist_ok=True)
            tmp = SECT_CONFIG + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(etat, f)
            os.replace(tmp, SECT_CONFIG)
        except (OSError, ValueError, TypeError, KeyError) as e:
            print("[ce_pc_plasma] rubriques :", e)

    @pyqtSlot(int, int, bool)
    def saveWindow(self, w, h, maximized):
        # Mémorise la taille. Fenêtre agrandie : on garde la dernière taille normale déjà connue.
        etat = load_window_state()
        if not maximized and 640 <= w <= 10000 and 460 <= h <= 10000:
            etat["w"], etat["h"] = int(w), int(h)
        etat["max"] = bool(maximized)
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            tmp = WIN_CONFIG + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(etat, f)
            os.replace(tmp, WIN_CONFIG)
        except OSError as e:
            print("[ce_pc_plasma] taille de la fenêtre :", e)

    @pyqtSlot(str)
    def launchApp(self, name):
        # Seuls ces programmes peuvent être lancés (barre, et Skanpage depuis la carte d'un scanner)
        if name not in ("systemsettings", "kinfocenter", "skanpage"):
            return
        try:
            lancer([name])
        except OSError:
            self.messageRequested.emit(tr("Program not found"),
                                       tr("The program “{name}” is not installed on this computer.").format(name=name))

    # einstellungsSprung : nur diese Module der Systemeinstellungen dürfen geöffnet werden
    SETTINGS_MODULES = {"kcm_gamecontroller", "kcm_keyboard", "kcm_mouse", "kcm_touchpad", "kcm_tablet",
                        "kcm_printer_manager"}
    _kcm_cache = {}

    @pyqtSlot(str, result=bool)
    def hasSettings(self, module):
        """Ist dieses Modul der Systemeinstellungen installiert? (Dateisuche, gemerkt ; kein Prozessstart)"""
        if module not in self.SETTINGS_MODULES:
            return False
        if module not in self._kcm_cache:
            import glob
            dirs = [os.path.expanduser("~/.local/share")] + (os.environ.get("XDG_DATA_DIRS") or
                                                              "/usr/local/share:/usr/share").split(":")
            treffer = any(os.path.isfile(os.path.join(d, "applications", module + ".desktop")) for d in dirs if d)
            treffer = treffer or bool(glob.glob("/usr/lib*/qt6/plugins/plasma/kcms/*/%s.so" % module)
                                      or glob.glob("/usr/lib/*/qt6/plugins/plasma/kcms/*/%s.so" % module))
            self._kcm_cache[module] = treffer
        return self._kcm_cache[module]

    @pyqtSlot(str)
    def openSettings(self, module):
        """Öffnet die Systemeinstellungen direkt bei diesem Modul (z. B. kcm_gamecontroller)."""
        if module not in self.SETTINGS_MODULES:
            return
        for cmd in (["systemsettings", module], ["kcmshell6", module]):
            try:
                lancer(cmd)
                return
            except OSError:
                continue
        self.messageRequested.emit(tr("Program not found"),
                                   tr("The program “{name}” is not installed on this computer.").format(name="systemsettings"))

    @pyqtSlot()
    def refreshAll(self):
        self._diskWake.set()
        self._netWake.set()
        self._prnWake.set()
        self._scanWake.set()

    @pyqtSlot(str, str, str)
    def listShares(self, host, user, password):
        # Liste les partages d'un serveur avec smbclient (en arrière-plan). Le mot de passe passe par
        # l'environnement du processus, jamais par la ligne de commande, et n'est pas conservé.
        host, user = host.strip(), user.strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]+", host):
            self.sharesError.emit(tr("The server address is empty or contains a forbidden character."))
            return
        if user and not re.fullmatch(r"[^/\\@:%\s]+", user):
            self.sharesError.emit(tr("The username contains a forbidden character."))
            return
        threading.Thread(target=self._listSharesWork, args=(host, user, password), daemon=True).start()

    def _listSharesWork(self, host, user, password):
        env = dict(os.environ)
        cmd = ["smbclient", "-g", "-L", "//" + host]
        if user:
            cmd += ["-U", user]
            env["PASSWD"] = password
        else:
            cmd += ["-N"]
        try:
            r = subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                               text=True, timeout=20)
        except FileNotFoundError:
            self.sharesError.emit(tr("The smbclient program is not installed (package “samba”). "
                                     "Type the share name by hand, or use the “Open” button after adding it."))
            return
        except subprocess.TimeoutExpired:
            self.sharesError.emit(tr("The server is not responding (timed out)."))
            return
        finally:
            env.pop("PASSWD", None)
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        shares = []
        for ligne in (r.stdout or "").splitlines():
            parts = ligne.split("|")
            if len(parts) >= 2 and parts[0] == "Disk" and parts[1] and not parts[1].endswith("$"):
                shares.append(parts[1])
        if shares:
            self.sharesFound.emit(shares)
            return
        if "LOGON_FAILURE" in out or "ACCESS_DENIED" in out:
            self.sharesError.emit(tr("Incorrect username or password."))
        elif "CONNECTION_REFUSED" in out or "UNREACHABLE" in out or "Connection to" in out:
            self.sharesError.emit(tr("Server unreachable. Check the address and that the server is turned on."))
        elif r.returncode == 0:
            self.sharesError.emit(tr("No share visible with these credentials."))
        else:
            self.sharesError.emit(tr("The search failed."))

    @pyqtSlot(str, str, str, str, str, bool)
    def addNetwork(self, name, host, share, user, password, remember):
        titre = tr("Cannot add")
        name, host, share, user = name.strip(), host.strip(), share.strip().strip("/"), user.strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]+", host):
            self.messageRequested.emit(titre, tr("The server address is empty or contains a forbidden character."))
            return
        if not share or any(c in share for c in "\\/") or len(share) > 80:
            self.messageRequested.emit(titre, tr("The share name is empty or contains a forbidden character."))
            return
        if not user:
            self.messageRequested.emit(titre, tr("The username is required."))
            return
        if not re.fullmatch(r"[^/\\@:%\s]+", user):
            self.messageRequested.emit(titre, tr("The username contains a forbidden character."))
            return
        locs = load_net_locations()
        if any(l["host"].lower() == host.lower() and l["share"].lower() == share.lower() for l in locs):
            self.messageRequested.emit(titre, tr("This location already exists in the list."))
            return
        if remember and not password:
            self.messageRequested.emit(titre, tr("Type the password to be able to remember it."))
            return
        nouveau = {"name": name, "host": host,
                   "share": share, "user": user}
        if remember:
            nouveau["retenir"] = True
        locs.append(nouveau)
        try:
            save_net_locations(locs)
        except OSError as e:
            self.messageRequested.emit(titre, tr("Could not save the list:\n{error}").format(error=e))
            return
        sync_places(locs)
        if remember:
            def _ranger():
                if not wallet_ecrire(wallet_cle(nouveau), password):
                    self.messageRequested.emit(tr("Password not remembered"),
                                               tr("KWallet could not save the password: "
                                                  "the gauge will not be shown."))
                _ESPACE.pop(net_url(nouveau), None)
                _PORTEFEUILLE["ko_jusqu"] = 0
                self._netWake.set()
            threading.Thread(target=_ranger, daemon=True).start()
        self._netWake.set()

    @pyqtSlot(str)
    def removeNetwork(self, url):
        retirees = [l for l in load_net_locations() if net_url(l) == url and l.get("retenir")]
        locs = [l for l in load_net_locations() if net_url(l) != url]
        try:
            save_net_locations(locs)
        except OSError as e:
            self.messageRequested.emit(tr("Cannot remove"), str(e))
            return
        for l in retirees:
            threading.Thread(target=wallet_ecrire, args=(wallet_cle(l), ""), daemon=True).start()
        sync_places(locs)
        self._netWake.set()

    @pyqtSlot(str)
    def ejectOptical(self, device):
        threading.Thread(target=self._ejectOptical, args=(device,), daemon=True).start()

    def _ejectOptical(self, device):
        try:
            r = subprocess.run(["eject", device], capture_output=True, text=True, timeout=30)
        except FileNotFoundError:
            self.messageRequested.emit(tr("Cannot eject"), tr("Program not found"))
            return
        except subprocess.TimeoutExpired:
            self.messageRequested.emit(tr("Cannot eject"), tr("unknown error"))
            return
        if r.returncode != 0:
            self.messageRequested.emit(tr("Cannot eject"), (r.stderr or "").strip() or tr("unknown error"))

    def _openOptical(self, device):
        # Disque présent mais pas monté : on le monte, puis on l'ouvre dans Dolphin
        if not disque_present(device):
            return
        self._mountOpen(device, True)

    @pyqtSlot(str)
    def mountDevice(self, device):
        threading.Thread(target=self._mountOpen, args=(device, False), daemon=True).start()

    def _mountOpen(self, device, ouvrir):
        """Monte un volume avec udisks (ggf. avec la fenêtre d'authentification de Plasma), puis l'ouvre si voulu."""
        titre = tr("Cannot open") if ouvrir else tr("Cannot mount")
        try:
            r = subprocess.run(["udisksctl", "mount", "-b", device],
                               capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            self.messageRequested.emit(titre, tr("Program not found"))
            return
        except subprocess.TimeoutExpired:
            self.messageRequested.emit(titre, tr("unknown error"))
            return
        if r.returncode == 0:
            m = re.search(r" at (.+?)\.?\s*$", (r.stdout or "").strip())
        else:   # « already mounted at `/run/media/…' » : on ouvre simplement le volume déjà monté
            m = re.search(r"already mounted at [`'\"](.+?)['\"]", r.stderr or "")
        if not m:
            detail = ((r.stderr or "") + (r.stdout or "")).strip() or tr("unknown error")
            self.messageRequested.emit(titre, detail)
            return
        self._diskWake.set()
        if ouvrir:
            self.openFolder(m.group(1))

    @pyqtSlot(str)
    def unmountNetwork(self, mountpoint):
        threading.Thread(target=self._unmountNetwork, args=(mountpoint,), daemon=True).start()

    def _unmountNetwork(self, mountpoint):
        titre = tr("Cannot disconnect")
        if not mountpoint.startswith("/"):
            return
        try:
            r = subprocess.run(["umount", mountpoint], capture_output=True, text=True, timeout=30)
        except FileNotFoundError:
            self.messageRequested.emit(titre, tr("Program not found"))
            return
        except subprocess.TimeoutExpired:
            self.messageRequested.emit(titre, tr("unknown error"))
            return
        if r.returncode != 0:
            self.messageRequested.emit(titre, (r.stderr or "").strip() or tr("unknown error"))
        self._netWake.set()
        self._diskWake.set()

    @pyqtSlot(str)
    def copyPath(self, path):
        QApplication.clipboard().setText(chemin_affiche(path))

    @pyqtSlot(str)
    def openTerminal(self, path):
        path = chemin_affiche(path)
        titre = tr("Cannot open terminal")
        if not os.path.isdir(path):
            self.messageRequested.emit(titre, tr("Folder not found"))
            return
        for cmd in (["konsole", "--workdir", path], ["xdg-terminal-exec"], ["x-terminal-emulator"]):
            try:
                lancer(cmd, cwd=path)
                return
            except FileNotFoundError:
                continue
            except OSError as e:
                self.messageRequested.emit(titre, str(e))
                return
        self.messageRequested.emit(titre, tr("No terminal program found"))

    @pyqtSlot(str, str)
    def ejectDevice(self, device, label):
        threading.Thread(target=self._eject, args=(device, label),
                         daemon=True).start()

    def _eject(self, device, label):
        titre = tr("Cannot eject")
        try:
            result = subprocess.run(
                ["udisksctl", "unmount", "-b", device],
                capture_output=True, text=True, timeout=15)
        except FileNotFoundError:
            self.messageRequested.emit(
                titre, tr("The udisksctl command was not found on this system."))
            return
        except subprocess.TimeoutExpired:
            self.messageRequested.emit(
                titre, tr("Unmounting {label} timed out.").format(label=label))
            return
        if result.returncode != 0:
            detail = result.stderr.strip() or tr("unknown error")
            self.messageRequested.emit(
                titre,
                tr("Could not unmount {label}:\n{detail}\n\n"
                   "Check that no file is still open on this drive.").format(label=label, detail=detail))
            return
        try:
            result = subprocess.run(
                ["udisksctl", "power-off", "-b", get_base_disk_device(device)],
                capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                detail = result.stderr.strip() or tr("unknown error")
                self.messageRequested.emit(
                    tr("Partial eject"),
                    tr("{label} was unmounted but could not be powered off:\n{detail}\n\n"
                       "You can still unplug it.").format(label=label, detail=detail))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    @pyqtSlot(str)
    def showSmart(self, device):
        threading.Thread(target=self._smart, args=(device,),
                         daemon=True).start()

    def _smart(self, device):
        base = get_base_disk_device(device)

        def run(cmd, timeout):
            return subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout)

        try:
            result = run(["smartctl", "-a", base], 30)
        except FileNotFoundError:
            self.messageRequested.emit(
                tr("SMART unavailable"),
                tr("The smartctl command was not found.\n\n"
                   "Install the smartmontools package to enable this feature."))
            return
        except subprocess.TimeoutExpired:
            self.messageRequested.emit(
                tr("SMART unavailable"), tr("Reading SMART timed out."))
            return

        combined = (result.stdout + result.stderr).lower()
        if "permission denied" in combined or "must be root" in combined:
            try:
                result = run(["pkexec", "smartctl", "-a", base], 90)
            except FileNotFoundError:
                self.messageRequested.emit(
                    tr("Insufficient rights"),
                    tr("Reading SMART requires root rights, and pkexec "
                       "(graphical elevation) was not found on this system."))
                return
            except subprocess.TimeoutExpired:
                self.messageRequested.emit(
                    tr("SMART unavailable"), tr("Reading SMART timed out."))
                return

        output = (result.stdout.strip() or result.stderr.strip()
                  or tr("No information available."))
        self.smartReady.emit("SMART - " + base, output)

    @pyqtSlot(str, result=str)
    def getLabel(self, device):
        try:
            return subprocess.check_output(
                ["lsblk", "-no", "LABEL", device],
                stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
        except Exception:
            return ""

    @pyqtSlot(str, str, str)
    def renameDevice(self, device, fstype, label):
        threading.Thread(target=self._rename, args=(device, fstype, label),
                         daemon=True).start()

    def _rename(self, device, fstype, label):
        titre = tr("Cannot rename")
        label = label.strip()
        fs = fstype.lower()
        limites = {"ntfs": 128, "vfat": 11, "exfat": 15,
                   "ext2": 16, "ext3": 16, "ext4": 16,
                   "btrfs": 255, "xfs": 12}
        a_chaud = {"ext2", "ext3", "ext4", "btrfs", "xfs"}

        if fs not in limites:
            self.messageRequested.emit(
                titre, tr("Renaming is not supported for this format ({fstype}).").format(fstype=fstype))
            return
        if not label or "/" in label or any(ord(c) < 32 for c in label):
            self.messageRequested.emit(
                titre, tr("The name is empty or contains a forbidden character."))
            return
        if len(label.encode("utf-8")) > limites[fs]:
            self.messageRequested.emit(
                titre, tr("The name is too long for this format (maximum {max} characters).").format(max=limites[fs]))
            return

        if fs not in a_chaud:
            try:
                r = subprocess.run(["udisksctl", "unmount", "-b", device],
                                   capture_output=True, text=True, timeout=15)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self.messageRequested.emit(titre, tr("Unmounting the disk failed."))
                return
            if r.returncode != 0:
                detail = r.stderr.strip() or tr("unknown error")
                self.messageRequested.emit(
                    titre,
                    tr("Could not unmount the disk:\n{detail}\n\n"
                       "Close the windows and applications that use this drive, then try again.").format(detail=detail))
                return

        obj = "/org/freedesktop/UDisks2/block_devices/" + os.path.basename(device)
        valeur = "'" + label.replace("\\", "\\\\").replace("'", "\\'") + "'"
        ok = False
        detail = ""
        try:
            r = subprocess.run(
                ["gdbus", "call", "--system", "--dest", "org.freedesktop.UDisks2",
                 "--object-path", obj,
                 "--method", "org.freedesktop.UDisks2.Filesystem.SetLabel",
                 valeur, "{}"],
                capture_output=True, text=True, timeout=30)
            ok = r.returncode == 0
            detail = r.stderr.strip() or tr("unknown error")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            detail = tr("gdbus not found or timed out.")

        if fs not in a_chaud:
            try:
                r = subprocess.run(["udisksctl", "mount", "-b", device],
                                   capture_output=True, text=True, timeout=15)
                if r.returncode != 0:
                    self.messageRequested.emit(
                        tr("Remount failed"),
                        tr("The disk could not be remounted:\n{detail}\n\n"
                           "Unplug it and plug it back in.").format(
                               detail=r.stderr.strip() or tr("unknown error")))
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        if not ok:
            self.messageRequested.emit(titre, detail)

    @pyqtSlot(str)
    def openFolder(self, path):
        if path.startswith("optical:"):
            threading.Thread(target=self._openOptical, args=(path[8:],), daemon=True).start()
            return
        if path.startswith("unmounted:"):   # nicht eingebundenes Volume : einbinden, dann öffnen
            threading.Thread(target=self._mountOpen, args=(path[10:], True), daemon=True).start()
            return
        path = chemin_affiche(path)
        try:
            lancer(["dolphin", "--new-window", path])
        except FileNotFoundError:
            try:
                lancer(["xdg-open", path])
            except Exception:
                print(f"Impossible d'ouvrir {path}")


QML = """
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Dialogs
import org.kde.kirigami as Kirigami

QQC2.ApplicationWindow {
    id: win
    visible: true
    title: trad("This PC")
    // minRuban : la fenêtre ne descend pas sous la largeur du ruban (elle dépend de la langue)
    minimumWidth: Math.max(740, ribbonRow.implicitWidth + 20)
    width: Math.max(minimumWidth, winInit.w > 0 ? winInit.w : 850)   // tailleInitiale
    // minHauteur : avec le ruban, il faut voir la première rangée de disques en entier
    minimumHeight: 520
    height: Math.max(520, winInit.h > 0 ? winInit.h : 584)
    // fenetreMemo : la taille est enregistrée à la fermeture (visibility 4 = fenêtre agrandie)
    onClosing: backend.saveWindow(win.width, win.height, win.visibility === 4)
    Component.onCompleted: {
        if (winInit.max)
            win.showMaximized()
        keyHandler.forceActiveFocus()
        probeRoots()
    }
    color: Kirigami.Theme.backgroundColor

    // rubriquesMemo (Ce PC 1.1) : repli de chaque rubrique et rubriques affichées, retenus d'une ouverture à l'autre
    property bool foldersCollapsed: sectInit.folders.collapsed
    property bool disksCollapsed: sectInit.disks.collapsed
    property bool netCollapsed: sectInit.net.collapsed
    property bool printersCollapsed: sectInit.printers.collapsed
    property bool foldersShown: sectInit.folders.shown
    property bool disksShown: sectInit.disks.shown
    property bool netShown: sectInit.net.shown
    property bool printersShown: sectInit.printers.shown
    property bool quickCollapsed: sectInit.quick.collapsed   // schnellzugriff : linke Leiste mit angehefteten Ordnern
    property bool quickShown: sectInit.quick.shown
    function saveSections() {
        backend.saveSections(JSON.stringify({
            folders: { collapsed: foldersCollapsed, shown: foldersShown },
            disks: { collapsed: disksCollapsed, shown: disksShown },
            net: { collapsed: netCollapsed, shown: netShown },
            printers: { collapsed: printersCollapsed, shown: printersShown },
            quick: { collapsed: quickCollapsed, shown: quickShown } }))
    }
    onFoldersCollapsedChanged: saveSections()
    onDisksCollapsedChanged: saveSections()
    onNetCollapsedChanged: saveSections()
    onPrintersCollapsedChanged: saveSections()
    onFoldersShownChanged: saveSections()
    onDisksShownChanged: saveSections()
    onNetShownChanged: saveSections()
    onPrintersShownChanged: saveSections()
    onQuickCollapsedChanged: saveSections()
    onQuickShownChanged: saveSections()
    // Nom d'une rubrique sans son compteur « ({n}) » (cases à cocher du groupe « Afficher »)
    function sectName(s) {
        return s.replace("({n})", "").replace("（{n}）", "").trim()
    }
    // seuilAlerte : au-delà de cette occupation (fraction du disque), les jauges passent au rouge et la carte affiche « ⚠ »
    readonly property real alertFrac: 0.8
    // couleursJauge : bleu des jauges normales et rouge des jauges en alerte (fixes)
    readonly property color gaugeBlue: "#1e88e5"
    readonly property color gaugeRed: "#d92b2b"
    // Disque ou emplacement réseau sélectionné par un clic (point de montage), vide si aucun
    property string selectedKey: ""

    property var propsDisk: ({})

    // grilleCartes : cartes de largeur fixe, autant de colonnes que la place le permet
    // (zone utile = largeur du défilement - 10 - marges 2 x 15 ; 8 d'espacement entre colonnes)
    readonly property real cardWidth: 340
    readonly property int cardCols: Math.max(1, Math.floor((scroll.availableWidth - 32) / (cardWidth + 8)))


    // fenestraLangues : texte traduit (table envoyée par le programme), texte anglais si absent
    function trad(s) {
        var v = trTable[s]
        return v !== undefined ? v : s
    }

    // Disque ou emplacement réseau actuellement sélectionné (null si rien)
    readonly property var selEntry: {
        var k = selectedKey
        if (k === "")
            return null
        for (var i = 0; i < backend.disks.length; i++)
            if (backend.disks[i].mountpoint === k)
                return backend.disks[i]
        for (var j = 0; j < backend.networks.length; j++)
            if (backend.networks[j].mountpoint === k)
                return backend.networks[j]
        return null
    }

    // taille : Go avec une décimale sous 1 To, puis To avec trois chiffres significatifs
    // einstellungsSprung : Gerätetyp -> Modul der Systemeinstellungen (Doppelklick / Rechtsklick auf der Karte)
    readonly property var kindModule: ({ keyboard: "kcm_keyboard", mouse: "kcm_mouse", touchpad: "kcm_touchpad",
                                         tablet: "kcm_tablet", gamepad: "kcm_gamecontroller" })
    function settingsModuleFor(d) {
        if (d.scanner === true)
            return ""
        if (d.indicator === true)
            return kindModule[d.kind] || ""
        return "kcm_printer_manager"
    }
    // seitenleiste : Baum « Dieser PC » (Laufwerke -> Ordner, Unterordner erst beim Aufklappen im Hintergrund geladen)
    property bool pcCollapsed: false
    // Breite der Seitenleiste : ihre rechte Kante (1 px Rahmen) liegt exakt auf der ersten Ribbon-Trennlinie,
    // auch bei anderer Sprache oder Schriftgröße (die Gruppe « Standort » wird dann breiter oder schmaler)
    property var firstGrp: null
    property var firstSep: null
    readonly property real sideWidth: (firstGrp && firstSep) ? Math.max(180, Math.round(ribbonRow.x + firstGrp.x + firstSep.x + 1)) : 240
    property string sideSelKey: ""   // zuletzt angeklickte Zeile der Seitenleiste (bleibt, bis eine andere angeklickt wird)
    property var treeOpen: ({})
    property var treeKids: ({})
    // Ein neues Zeilenmodell setzt die ListView nach oben : Scrollposition merken und danach wiederherstellen
    // Das neue Modell setzt contentY erst NACH der Änderung (im nächsten Bild) zurück : die gemerkte Position wird deshalb
    // von einem kurzen Timer ein paarmal wieder eingesetzt. Läuft die Wiederherstellung schon (z. B. kommt die
    // Unterordner-Liste kurz nach dem Klick), bleibt die zuerst gemerkte Position erhalten.
    property real pendingY: -1
    Timer {
        id: scrollRestore
        interval: 70
        repeat: true
        property int runs: 0
        onTriggered: {
            if (win.pendingY >= 0)
                sideList.contentY = Math.min(win.pendingY, Math.max(0, sideList.contentHeight - sideList.height))
            if (++runs >= 4) {
                stop()
                win.pendingY = -1
            }
        }
    }
    function keepSideScroll(aendern) {
        if (pendingY < 0)
            pendingY = sideList.contentY
        scrollRestore.runs = 0
        scrollRestore.restart()
        aendern()
    }
    function toggleNode(path) {
        keepSideScroll(function() { toggleNodeNow(path) })
    }
    function toggleNodeNow(path) {
        var o = Object.assign({}, treeOpen)
        if (o[path]) {
            delete o[path]
        } else {
            o[path] = true
            backend.listDirs(path)   // immer neu lesen ; bis die Antwort kommt, bleibt der alte Stand sichtbar
        }
        treeOpen = o
    }
    Connections {
        target: backend
        function onDirsListed(path, list) {
            win.keepSideScroll(function() {
                var k = Object.assign({}, win.treeKids)
                k[path] = list
                win.treeKids = k
            })
        }
        function onDisksChanged() { win.probeRoots() }
    }
    // Eine flache Liste aller sichtbaren Zeilen (Kopf, Pin, Hinweis, Baumknoten) ; hängt an allem, was sie liest
    readonly property var sidebarRows: {
        var rows = []
        rows.push({ type: "head", key: "quick", label: trad("Quick access"), icon: "starred-symbolic",
                    collapsed: quickCollapsed, canAdd: true })
        var ps = backend.pins
        if (!quickCollapsed) {
            for (var i = 0; i < ps.length; i++)
                rows.push({ type: "pin", path: ps[i].path, label: ps[i].label, icon: ps[i].icon,
                            exists: ps[i].exists, pinIndex: i, pinCount: ps.length })
            if (ps.length === 0)
                rows.push({ type: "hint" })
        }
        rows.push({ type: "head", key: "pc", label: trad("This PC"), icon: "computer", collapsed: pcCollapsed })
        if (!pcCollapsed) {
            var ds = backend.disks
            for (var j = 0; j < ds.length; j++) {
                var d = ds[j]
                if (d.mountpoint.charAt(0) !== "/" || d.isUnmounted === true || d.isOptical === true)
                    continue
                addNode(rows, backend.displayPath(d.mountpoint), d.label, d.icon, 0, true)
            }
        }
        return rows
    }
    // hasKids : Antwort der Vorabprüfung des Elternordners (true = hat Unterordner oder unbekannt). Ist der Ordner selbst
    // schon gelesen, gilt dessen Liste ; so zeigt nur ein Ordner mit echten Unterordnern den Pfeil.
    function addNode(rows, path, label, icon, depth, hasKids) {
        var open = treeOpen[path] === true
        var kids = treeKids[path]
        rows.push({ type: "node", path: path, label: label, icon: icon, depth: depth, open: open,
                    expandable: kids !== undefined ? kids.length > 0 : hasKids !== false,
                    loading: open && kids === undefined })
        if (open && kids !== undefined)
            for (var i = 0; i < kids.length; i++)
                addNode(rows, kids[i].path, kids[i].name, "folder", depth + 1, kids[i].hasKids)
    }
    // Laufwerks-Wurzeln gleich lesen, damit auch ein leerer Stick keinen unnötigen Pfeil zeigt
    function probeRoots() {
        var ds = backend.disks
        for (var j = 0; j < ds.length; j++) {
            var d = ds[j]
            if (d.mountpoint.charAt(0) !== "/" || d.isUnmounted === true || d.isOptical === true)
                continue
            var pth = backend.displayPath(d.mountpoint)
            if (treeKids[pth] === undefined)
                backend.listDirs(pth)
        }
    }
    // schnellzugriff : ist dieser Pfad angeheftet? (liest backend.pins, daher reagieren Menütexte sofort)
    function isPinned(path) {
        var k = path.length > 1 ? path.replace(/[/]+$/, "") : path
        var ps = backend.pins
        for (var i = 0; i < ps.length; i++) {
            var q = ps[i].path
            if ((q.length > 1 ? q.replace(/[/]+$/, "") : q) === k)
                return true
        }
        return false
    }
    // rateText : Durchsatz lesbar (B/s … GB/s)
    function rateText(n) {
        var u = ["B/s", "KB/s", "MB/s", "GB/s"], i = 0
        while (n >= 1024 && i < 3) { n /= 1024; i++ }
        return (i === 0 ? Math.round(n) : n.toFixed(1)).toString().replace(".", trDecimal) + " " + u[i]
    }
    function taille(n) {
        var g = n / 1073741824
        if (Math.round(g * 10) / 10 < 1024)
            return g.toFixed(1).replace(".", trDecimal) + " " + trad("GB")
        var t = g / 1024
        return t.toFixed(t < 10 ? 2 : (t < 100 ? 1 : 0)).replace(".", trDecimal) + " " + trad("TB")
    }
    // Tastatur : Pfeile wählen ein Laufwerk/einen Ort, Enter öffnet, F5 aktualisiert, Esc hebt die Auswahl auf,
    // Strg+C kopiert den Pfad. Das Element unten hat nur Fokus, solange kein Dialog/Menü offen ist.
    function moveSel(dx, dy) {
        var secs = []
        if (disksShown && !disksCollapsed && backend.disks.length > 0)
            secs.push(backend.disks)
        if (netShown && !netCollapsed && backend.networks.length > 0)
            secs.push(backend.networks)
        if (secs.length === 0)
            return
        var s = -1, i = -1
        for (var a = 0; a < secs.length && s < 0; a++) {
            for (var b = 0; b < secs[a].length; b++) {
                if (secs[a][b].mountpoint === selectedKey) {
                    s = a
                    i = b
                    break
                }
            }
        }
        if (s < 0) {
            selectedKey = secs[0][0].mountpoint
            return
        }
        var cols = cardCols
        var col = i % cols
        if (dx !== 0) {
            var j = i + dx
            if (j >= 0 && j < secs[s].length)
                selectedKey = secs[s][j].mountpoint
            else if (j < 0 && s > 0)
                selectedKey = secs[s - 1][secs[s - 1].length - 1].mountpoint
            else if (j >= secs[s].length && s < secs.length - 1)
                selectedKey = secs[s + 1][0].mountpoint
        } else if (dy > 0) {
            var k = i + cols
            if (k < secs[s].length)
                selectedKey = secs[s][k].mountpoint
            else if (s < secs.length - 1)
                selectedKey = secs[s + 1][Math.min(col, secs[s + 1].length - 1)].mountpoint
        } else if (dy < 0) {
            var k2 = i - cols
            if (k2 >= 0) {
                selectedKey = secs[s][k2].mountpoint
            } else if (s > 0) {
                var p = secs[s - 1]
                var lastRow = Math.floor((p.length - 1) / cols) * cols
                selectedKey = p[Math.min(lastRow + col, p.length - 1)].mountpoint
            }
        }
    }
    function handleKey(ev) {
        if (ev.key === Qt.Key_F5) {
            backend.refreshAll()
        } else if (ev.key === Qt.Key_Return || ev.key === Qt.Key_Enter) {
            barRoot.runCmd("open")
        } else if (ev.key === Qt.Key_Escape) {
            selectedKey = ""
        } else if (ev.key === Qt.Key_Left) {
            moveSel(-1, 0)
        } else if (ev.key === Qt.Key_Right) {
            moveSel(1, 0)
        } else if (ev.key === Qt.Key_Up) {
            moveSel(0, -1)
        } else if (ev.key === Qt.Key_Down) {
            moveSel(0, 1)
        } else if (ev.key === Qt.Key_C && (ev.modifiers & Qt.ControlModifier)) {
            if (selEntry !== null && selEntry.mountpoint.charAt(0) === "/")
                backend.copyPath(selEntry.mountpoint)
        } else {
            ev.accepted = false
            return
        }
        ev.accepted = true
    }
    Item {
        id: keyHandler
        width: 0
        height: 0
        focus: true
        Keys.onPressed: function(event) { win.handleKey(event) }
    }
    function showPrinter(d) {
        printerDialog.info = d
        printerDialog.open()
    }
    function showProps(d) {
        propsDisk = d
        if (d.isUsb === true) {
            renameField.initial = d.rawLabel || ""
            renameField.text = renameField.initial
        }
        propsDialog.open()
    }

    QQC2.Dialog {
        id: propsDialog
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        title: win.trad("Properties of {name}").replace("{name}", win.propsDisk.label || "")
        width: 460
        standardButtons: QQC2.Dialog.Close

        contentItem: ColumnLayout {
            spacing: 12

            GridLayout {
                columns: 2
                columnSpacing: 14
                rowSpacing: 6
                Layout.fillWidth: true

                QQC2.Label { text: win.trad("Type:"); opacity: 0.75 }
                QQC2.Label {
                    text: win.propsDisk.isNetwork ? win.trad("Network location") : (win.propsDisk.isOptical === true ? win.trad("CD/DVD Drive") : (win.propsDisk.isUsb ? win.trad("Removable disk") : win.trad("Local Disk")))
                    Layout.fillWidth: true
                }
                QQC2.Label { text: win.trad("File system:"); opacity: 0.75 }
                QQC2.Label { text: win.propsDisk.fstype || ""; Layout.fillWidth: true }
                QQC2.Label { text: win.trad("Mount point:"); opacity: 0.75 }
                QQC2.Label {
                    text: win.propsDisk.mountpoint || ""
                    Layout.fillWidth: true
                    elide: Text.ElideMiddle
                }
                QQC2.Label { text: win.trad("Device:"); opacity: 0.75 }
                QQC2.Label { text: win.propsDisk.device || ""; Layout.fillWidth: true }
                QQC2.Label {
                    visible: backend.temps[win.propsDisk.device || ""] !== undefined
                    text: win.trad("Temperature:")
                    opacity: 0.75
                }
                QQC2.Label {
                    visible: backend.temps[win.propsDisk.device || ""] !== undefined
                    text: visible ? backend.temps[win.propsDisk.device].c.toFixed(1).replace(".", trDecimal) + " °C" : ""
                    Layout.fillWidth: true
                }
            }

            Kirigami.Separator { Layout.fillWidth: true }

            RowLayout {
                spacing: 20
                Layout.alignment: Qt.AlignHCenter

                Item {
                    id: pie
                    Layout.preferredWidth: 100
                    Layout.preferredHeight: 100
                    property real frac: win.propsDisk.total > 0
                                        ? win.propsDisk.used / win.propsDisk.total : 0
                    property color usedColor: frac >= win.alertFrac ? win.gaugeRed
                                                                    : win.gaugeBlue
                    property color freeColor: Kirigami.Theme.alternateBackgroundColor
                    property color lineColor: Qt.rgba(Kirigami.Theme.textColor.r,
                                                      Kirigami.Theme.textColor.g,
                                                      Kirigami.Theme.textColor.b, 0.35)
                    // donutAnim : der Ring läuft beim Öffnen und bei Änderungen sanft auf den Wert
                    property real shownFrac: 0
                    onFracChanged: shownFrac = frac
                    Component.onCompleted: shownFrac = frac
                    Behavior on shownFrac { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }
                    Behavior on usedColor { ColorAnimation { duration: 300 } }

                    Shape {
                        anchors.fill: parent
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {   // Spur (freier Platz)
                            strokeColor: pie.freeColor
                            strokeWidth: 12
                            fillColor: "transparent"
                            capStyle: ShapePath.FlatCap
                            PathAngleArc {
                                centerX: pie.width / 2; centerY: pie.height / 2
                                radiusX: 44; radiusY: 44
                                startAngle: -90; sweepAngle: 359.99
                            }
                        }
                        ShapePath {   // belegter Anteil
                            strokeColor: pie.usedColor
                            strokeWidth: 12
                            fillColor: "transparent"
                            capStyle: ShapePath.RoundCap
                            PathAngleArc {
                                centerX: pie.width / 2; centerY: pie.height / 2
                                radiusX: 44; radiusY: 44
                                startAngle: -90; sweepAngle: 359.99 * pie.shownFrac
                            }
                        }
                    }
                    QQC2.Label {   // Prozentwert in der Mitte
                        anchors.centerIn: parent
                        text: Math.round(pie.shownFrac * 100) + " %"
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize + 2
                        font.weight: Font.DemiBold
                    }
                }

                ColumnLayout {
                    spacing: 6
                    RowLayout {
                        spacing: 8
                        Rectangle { width: 10; height: 10; color: pie.usedColor }
                        QQC2.Label { text: win.trad("Used: {size}").replace("{size}", win.taille(win.propsDisk.used || 0)) }
                    }
                    RowLayout {
                        spacing: 8
                        Rectangle {
                            width: 10; height: 10
                            color: Kirigami.Theme.alternateBackgroundColor
                            border.width: 1
                            border.color: pie.lineColor
                        }
                        QQC2.Label { text: win.trad("Free: {size}").replace("{size}", win.taille(win.propsDisk.free || 0)) }
                    }
                    RowLayout {
                        spacing: 8
                        Rectangle {
                            width: 10; height: 10
                            color: Kirigami.Theme.backgroundColor
                            border.width: 1
                            border.color: pie.lineColor
                        }
                        QQC2.Label { text: win.trad("Capacity: {size}").replace("{size}", win.taille(win.propsDisk.total || 0)) }
                    }
                }
            }

            QQC2.Button {
                text: win.trad("SMART status…")
                visible: !win.propsDisk.isNetwork && win.propsDisk.isOptical !== true
                Layout.alignment: Qt.AlignHCenter
                onClicked: backend.showSmart(win.propsDisk.device)
            }

            RowLayout {
                visible: win.propsDisk.isUsb === true && win.propsDisk.mountpoint !== "/"
                         && !win.propsDisk.isNetwork
                Layout.fillWidth: true
                spacing: 8

                QQC2.TextField {
                    id: renameField
                    Layout.fillWidth: true
                    placeholderText: win.trad("Volume name")
                    property string initial: ""
                }
                QQC2.Button {
                    text: win.trad("Rename")
                    enabled: renameField.text.trim() !== "" && renameField.text !== renameField.initial
                    onClicked: {
                        backend.renameDevice(win.propsDisk.device, win.propsDisk.fstype,
                                             renameField.text)
                        propsDialog.close()
                    }
                }
            }
        }
    }

    QQC2.Dialog {
        id: smartDialog
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        width: 640
        height: 460
        standardButtons: QQC2.Dialog.Close

        contentItem: QQC2.ScrollView {
            QQC2.TextArea {
                id: smartText
                readOnly: true
                wrapMode: TextEdit.NoWrap
                font.family: "monospace"
                font.pointSize: Kirigami.Theme.smallFont.pointSize
            }
        }
    }

    Connections {
        target: backend
        function onRaiseRequested() {   // zweiter Start : vorhandenes Fenster zeigen (3 = minimiert)
            if (win.visibility === 3 || !win.visible)
                win.showNormal()
            win.raise()
            win.requestActivate()
        }
        function onSmartReady(titre, texte) {
            smartDialog.title = titre
            smartText.text = texte
            smartDialog.open()
        }
        function onNetworksChanged() {
            if (!propsDialog.visible)
                return
            for (var k = 0; k < backend.networks.length; k++) {
                if (backend.networks[k].mountpoint === win.propsDisk.mountpoint) {
                    win.propsDisk = backend.networks[k]
                    break
                }
            }
        }
        function onDisksChanged() {
            if (!propsDialog.visible)
                return
            for (var i = 0; i < backend.disks.length; i++) {
                if (backend.disks[i].mountpoint === win.propsDisk.mountpoint) {
                    win.propsDisk = backend.disks[i]
                    break
                }
            }
        }
    }

    QQC2.Dialog {
        id: msgDialog
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        standardButtons: QQC2.Dialog.Ok
        width: 400
        QQC2.Label {
            id: msgLabel
            width: parent.width
            wrapMode: Text.Wrap
        }
    }
    Connections {
        target: backend
        function onSharesFound(liste) {
            addNetDialog.busy = false
            addNetDialog.msg = ""
            addNetDialog.found = liste
            netFound.currentIndex = -1
        }
        function onSharesError(texte) {
            addNetDialog.busy = false
            addNetDialog.found = []
            addNetDialog.msg = texte
        }
        function onMessageRequested(titre, texte) {
            msgDialog.title = titre
            msgLabel.text = texte
            msgDialog.open()
        }
    }

    QQC2.Dialog {
        id: addNetDialog
        property var found: []
        property string msg: ""
        property bool busy: false
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        title: win.trad("Add a network location")
        width: 480
        standardButtons: QQC2.Dialog.Ok | QQC2.Dialog.Cancel
        onAboutToShow: {
            netName.text = ""
            netHost.text = ""
            netShare.text = ""
            netUser.text = ""
            netPass.text = ""
            netRemember.checked = false
            addNetDialog.found = []
            addNetDialog.msg = ""
            addNetDialog.busy = false
        }
        onClosed: netPass.text = ""
        onAccepted: backend.addNetwork(netName.text, netHost.text, netShare.text, netUser.text,
                                       netPass.text, netRemember.checked)

        contentItem: GridLayout {
            columns: 2
            columnSpacing: 12
            rowSpacing: 8

            QQC2.Label { text: win.trad("Server address:"); opacity: 0.75 }
            QQC2.TextField {
                id: netHost
                Layout.fillWidth: true
                placeholderText: win.trad("192.168.1.10, nas-name or smb://...")
                onTextChanged: {
                    // Adresse collée : smb://utilisateur@serveur/partage
                    var m = /^ *smb:[/][/](?:([^@/]+)@)?([^/ ]+)(?:[/]([^/ ]+))?/i.exec(text)
                    if (m) {
                        var u = m[1] ? m[1] : ""
                        try { u = decodeURIComponent(u) } catch (e) {}
                        var s = m[3] ? m[3] : ""
                        try { s = decodeURIComponent(s) } catch (e) {}
                        netUser.text = u !== "" ? u : netUser.text
                        if (s !== "")
                            netShare.text = s
                        text = m[2]
                    }
                }
            }
            QQC2.Label { text: win.trad("Username (required):"); opacity: 0.75 }
            QQC2.TextField { id: netUser; Layout.fillWidth: true }
            QQC2.Label { text: win.trad("Password:"); opacity: 0.75 }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                QQC2.TextField {
                    id: netPass
                    Layout.fillWidth: true
                    echoMode: TextInput.Password
                    placeholderText: win.trad("only for “List”, never saved")
                }
                QQC2.Button {
                    text: addNetDialog.busy ? win.trad("Searching…") : win.trad("List")
                    enabled: !addNetDialog.busy && netHost.text.trim() !== "" && netUser.text.trim() !== ""
                    onClicked: {
                        addNetDialog.msg = ""
                        addNetDialog.found = []
                        addNetDialog.busy = true
                        backend.listShares(netHost.text, netUser.text, netPass.text)
                    }
                }
            }
            QQC2.Label { text: win.trad("Shares found:"); opacity: 0.75; visible: addNetDialog.found.length > 0 }
            QQC2.ComboBox {
                id: netFound
                Layout.fillWidth: true
                visible: addNetDialog.found.length > 0
                model: addNetDialog.found
                currentIndex: -1
                displayText: currentIndex < 0 ? win.trad("Choose a share…") : currentText
                onActivated: netShare.text = currentText
            }
            QQC2.Label { text: win.trad("Share name (required):"); opacity: 0.75 }
            QQC2.TextField { id: netShare; Layout.fillWidth: true; placeholderText: win.trad("filled in from the list, or type it") }
            QQC2.Label { text: win.trad("Display name (optional):"); opacity: 0.75 }
            QQC2.TextField { id: netName; Layout.fillWidth: true; placeholderText: win.trad("My NAS") }
            QQC2.CheckBox {
                id: netRemember
                Layout.columnSpan: 2
                Layout.fillWidth: true
                enabled: netPass.text !== ""
                text: win.trad("Remember the password (KWallet) to show the free space")
            }
            QQC2.Label {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                visible: addNetDialog.msg !== ""
                wrapMode: Text.Wrap
                color: Kirigami.Theme.negativeTextColor
                text: addNetDialog.msg
            }
            QQC2.Label {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                opacity: 0.75
                text: win.trad("The final password is requested by Dolphin the first time you open it; you can ask it to remember it.")
            }
        }
    }

    // imprimantesInfo : fenêtre d'information sur une imprimante (lecture seule)
    QQC2.Dialog {
        id: printerDialog
        property var info: ({})
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        title: info.label || ""
        width: 460
        standardButtons: QQC2.Dialog.Close

        contentItem: GridLayout {
            columns: 2
            columnSpacing: 12
            rowSpacing: 8

            QQC2.Label { text: win.trad("Type:"); opacity: 0.75 }
            QQC2.Label { text: win.trad("Printer"); Layout.fillWidth: true }
            QQC2.Label { text: win.trad("Status:"); opacity: 0.75 }
            QQC2.Label { text: printerDialog.info.statusText || ""; Layout.fillWidth: true }
            QQC2.Label { text: win.trad("Device:"); opacity: 0.75 }
            QQC2.Label {
                text: printerDialog.info.device || ""
                Layout.fillWidth: true
                wrapMode: Text.WrapAnywhere
            }
            QQC2.Button {
                visible: printerDialog.info.absent === true
                Layout.columnSpan: 2
                text: win.trad("Remove from list")
                onClicked: {
                    backend.forgetPrinter(printerDialog.info.name)
                    printerDialog.close()
                }
            }
            ColumnLayout {
                visible: (printerDialog.info.inks || []).length > 0
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.topMargin: 6
                spacing: 6

                QQC2.Label { text: win.trad("Ink levels"); opacity: 0.75 }
                Repeater {
                    model: printerDialog.info.inks || []
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        QQC2.Label {
                            text: modelData.name
                            font: Kirigami.Theme.smallFont
                            elide: Text.ElideRight
                            Layout.preferredWidth: 150
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 10
                            color: Qt.tint(Kirigami.Theme.backgroundColor,
                                           Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                   Kirigami.Theme.textColor.b, 0.16))
                            border.width: 1
                            border.color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                  Kirigami.Theme.textColor.b, 0.38)
                            Rectangle {
                                x: 1; y: 1
                                width: (parent.width - 2) * modelData.level / 100
                                height: parent.height - 2
                                color: modelData.color
                            }
                        }
                        QQC2.Label {
                            text: modelData.level + " %"
                            font: Kirigami.Theme.smallFont
                            color: modelData.low ? win.gaugeRed : Kirigami.Theme.textColor
                            horizontalAlignment: Text.AlignRight
                            Layout.preferredWidth: 40
                        }
                    }
                }
            }
        }
    }

    // aProposDialog : fenêtre « À propos de Ce PC »
    QQC2.Dialog {
        id: aboutDialog
        modal: true
        anchors.centerIn: QQC2.Overlay.overlay
        title: win.trad("About This PC")
        width: 460
        standardButtons: QQC2.Dialog.Close

        contentItem: ColumnLayout {
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                Image {
                    visible: aboutInfo.icon !== ""
                    source: aboutInfo.icon
                    Layout.preferredWidth: 56
                    Layout.preferredHeight: 56
                    sourceSize.width: 112
                    sourceSize.height: 112
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    mipmap: true
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    QQC2.Label {
                        text: win.trad("This PC")
                        font.pixelSize: 22
                        font.bold: true
                    }
                    QQC2.Label {
                        text: win.trad("Version {version} · Plasma version").replace("{version}", aboutInfo.version)
                        opacity: 0.75
                    }
                }
            }

            Kirigami.Separator { Layout.fillWidth: true }

            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: win.trad("Part of the Fenestra series, which gives KDE Plasma the look of a Windows 11 desktop.")
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: win.trad("Author: {author}").replace("{author}", aboutInfo.auteur)
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                visible: aboutInfo.licence !== ""
                text: win.trad("License: {license}").replace("{license}", aboutInfo.licence)
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                opacity: 0.75
                text: win.trad("This software is neither affiliated with nor endorsed by Microsoft Corporation. Windows is a trademark of Microsoft Corporation.")
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                opacity: 0.75
                text: win.trad("Command bar icons: Fluent UI System Icons, © Microsoft Corporation, MIT license.")
            }

            // miseAJour (1.1)
            QQC2.CheckBox {
                Layout.fillWidth: true
                visible: backend.updateSupported
                text: win.trad("Check for a new version once a week")
                checked: backend.updateCheck
                onToggled: backend.setUpdateCheck(checked)
            }

            Kirigami.Separator { Layout.fillWidth: true }

            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                font: Kirigami.Theme.smallFont
                opacity: 0.65
                text: "Qt " + aboutInfo.qt + " · PyQt6 " + aboutInfo.pyqt + " · Python " + aboutInfo.python
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // barreRuban : barre de commandes en ruban (Ce PC 1.1 : le mode simple a été retiré)
        Item {
            id: barRoot
            // couleursBarre : couleurs « En-tête » du thème (comme la bande des menus de Dolphin)
            Kirigami.Theme.colorSet: Kirigami.Theme.Header
            Kirigami.Theme.inherit: false
            Layout.fillWidth: true
            Layout.preferredHeight: 118
            readonly property var sel: win.selEntry
            readonly property bool canOpen: sel !== null && sel.available !== false
            readonly property bool canProps: sel !== null && sel.isUnmounted !== true
                && (sel.isNetwork !== true || sel.mounted === true || sel.total > 0)

            function runCmd(a) {
                if (a === "add")
                    addNetDialog.open()
                else if (a === "open") {
                    if (canOpen)
                        backend.openFolder(sel.mountpoint)
                } else if (a === "props") {
                    if (canProps)
                        win.showProps(sel)
                } else if (a === "refresh")
                    backend.refreshAll()
                else if (a === "settings")
                    backend.launchApp("systemsettings")
                else if (a === "info")
                    backend.launchApp("kinfocenter")
                else if (a === "about")
                    aboutDialog.open()
            }
            Rectangle {
                anchors.fill: parent
                color: Kirigami.Theme.backgroundColor
            }

            // ===== RUBAN ===== (Ce PC 1.1 : seul mode de la barre)
            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Groupes du ruban
                RowLayout {
                    id: ribbonRow
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.topMargin: 6
                    Layout.leftMargin: 10
                    Layout.rightMargin: 10
                    Layout.bottomMargin: 4
                    spacing: 0

                    Repeater {
                        model: [
                            { g: win.trad("Location"), items: [
                                { t: win.trad("Properties"), i: "props", a: "props", w: 84 },
                                { t: win.trad("Open"), i: "open", a: "open", w: 72 },
                                { t: win.trad("Refresh"), i: "refresh", a: "refresh", w: 84 } ] },
                            { g: win.trad("Network"), items: [
                                { t: win.trad("Add a network location"), i: "add", a: "add", w: 112 } ] },
                            { g: win.trad("System"), items: [
                                { t: win.trad("System Settings"), i: "settings", a: "settings", w: 100 },
                                { t: win.trad("System information"), i: "info", a: "info", w: 100 },
                                { t: win.trad("About"), i: "about", a: "about", w: 84 } ] }
                        ]
                        delegate: RowLayout {
                            id: grp
                            Layout.fillHeight: true
                            spacing: 0

                            ColumnLayout {
                                Layout.fillHeight: true
                                spacing: 2

                                Row {
                                    Layout.alignment: Qt.AlignHCenter
                                    spacing: 2
                                    Repeater {
                                        model: modelData.items
                                        delegate: Item {
                                            id: bBtn
                                            readonly property bool usable: modelData.a === "open" ? barRoot.canOpen
                                                : (modelData.a === "props" ? barRoot.canProps : true)
                                            width: modelData.w
                                            height: 84

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: 5
                                                visible: bBtn.usable && (bMouse.containsMouse || bMouse.pressed)
                                                color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                                               Kirigami.Theme.highlightColor.b, bMouse.pressed ? 0.28 : 0.14)
                                                border.width: 1
                                                border.color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                                                      Kirigami.Theme.highlightColor.b, 0.5)
                                            }
                                            Item {
                                                id: bIcon
                                                x: (parent.width - width) / 2
                                                y: 8
                                                width: 32
                                                height: 32
                                                opacity: bBtn.usable ? 1.0 : 0.45
                                                readonly property string src: barIconsRuban[modelData.i] || modelData.i
                                                readonly property bool isFile: src.indexOf("file://") === 0
                                                Image {
                                                    anchors.fill: parent
                                                    visible: bIcon.isFile
                                                    source: bIcon.isFile ? bIcon.src : ""
                                                    sourceSize.width: 64
                                                    sourceSize.height: 64
                                                    fillMode: Image.PreserveAspectFit
                                                    smooth: true
                                                    mipmap: true
                                                }
                                                Kirigami.Icon {
                                                    anchors.fill: parent
                                                    visible: !bIcon.isFile
                                                    source: bIcon.isFile ? "" : bIcon.src
                                                }
                                            }
                                            QQC2.Label {
                                                x: 4
                                                y: 46
                                                width: parent.width - 8
                                                height: 34
                                                text: modelData.t
                                                wrapMode: Text.Wrap
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignTop
                                                elide: Text.ElideRight
                                                maximumLineCount: 2
                                                font: Kirigami.Theme.smallFont
                                                color: Kirigami.Theme.textColor
                                                opacity: bBtn.usable ? 1.0 : 0.45
                                            }
                                            MouseArea {
                                                id: bMouse
                                                anchors.fill: parent
                                                enabled: bBtn.usable
                                                hoverEnabled: true
                                                onClicked: barRoot.runCmd(modelData.a)
                                            }
                                        }
                                    }
                                }
                                Item { Layout.fillHeight: true }   // titresAlignes (1.1) : titre du groupe en bas du ruban
                                QQC2.Label {
                                    Layout.alignment: Qt.AlignHCenter
                                    text: modelData.g
                                    font: Kirigami.Theme.smallFont
                                    opacity: 0.65
                                    color: Kirigami.Theme.textColor
                                }
                            }

                            Rectangle {
                                id: grpSep
                                Layout.preferredWidth: 1
                                Layout.fillHeight: true
                                Layout.topMargin: 6
                                Layout.bottomMargin: 6
                                Layout.leftMargin: 8
                                Layout.rightMargin: 8
                                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                               Kirigami.Theme.textColor.b, 0.2)
                                // Die Seitenleiste endet genau auf der ersten Trennlinie (neben « Aktualisieren »)
                                Component.onCompleted: if (index === 0) { win.firstGrp = grp; win.firstSep = grpSep }
                            }
                        }
                    }

                    // groupeAfficher (Ce PC 1.1) : une case par rubrique, décochée = rubrique masquée
                    ColumnLayout {
                        Layout.fillHeight: true
                        spacing: 2

                        // casesAfficher : 1re colonne Dossiers / Périphériques / Réseau, Imprimantes à droite
                        // de Dossiers ; la 1re ligne est au niveau des icônes des boutons (y = 8)
                        Item {
                            Layout.preferredHeight: 84
                            Layout.preferredWidth: casesGrid.implicitWidth + 8
                            Grid {
                                id: casesGrid
                                x: 4
                                y: 8
                                flow: Grid.TopToBottom
                                rows: 3
                                columnSpacing: 14
                                rowSpacing: 2
                                Repeater {
                                    model: [
                                        { t: win.trad("Folders ({n})"), k: "folders" },
                                        { t: win.trad("Devices and drives ({n})"), k: "disks" },
                                        { t: win.trad("Network locations ({n})"), k: "net" },
                                        { t: win.trad("Printers and devices ({n})"), k: "printers" },
                                        { t: win.trad("Quick access ({n})"), k: "quick" }
                                    ]
                                    delegate: QQC2.CheckBox {
                                        topPadding: 0
                                        bottomPadding: 0
                                        font: Kirigami.Theme.smallFont
                                        text: win.sectName(modelData.t)
                                        checked: win[modelData.k + "Shown"]
                                        onToggled: win[modelData.k + "Shown"] = checked
                                    }
                                }
                            }
                        }
                        Item { Layout.fillHeight: true }   // titresAlignes (1.1)
                        QQC2.Label {
                            Layout.alignment: Qt.AlignHCenter
                            text: win.trad("Show")
                            font: Kirigami.Theme.smallFont
                            opacity: 0.65
                            color: Kirigami.Theme.textColor
                        }
                    }
                    Rectangle {
                        Layout.preferredWidth: 1
                        Layout.fillHeight: true
                        Layout.topMargin: 6
                        Layout.bottomMargin: 6
                        Layout.leftMargin: 8
                        Layout.rightMargin: 8
                        color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                       Kirigami.Theme.textColor.b, 0.2)
                    }

                    Item { Layout.fillWidth: true }
                }
            }
        }
        Kirigami.Separator { Layout.fillWidth: true }

        // miseAJour (1.1) : bandeau « nouvelle version disponible » (rien ne s'installe tout seul)
        Kirigami.InlineMessage {
            id: majBandeau
            property string version: ""
            property string adresse: ""
            Layout.fillWidth: true
            Layout.margins: 8
            type: Kirigami.MessageType.Information
            showCloseButton: true
            visible: false
            text: win.trad("Version {version} of This PC is available. To update, download it and run ./install.sh again.").replace("{version}", version)
            actions: [
                Kirigami.Action {
                    text: win.trad("View")
                    icon.name: "internet-web-browser"
                    onTriggered: Qt.openUrlExternally(majBandeau.adresse)
                }
            ]
            Connections {
                target: backend
                function onUpdateAvailable(version, adresse) {
                    majBandeau.version = version
                    majBandeau.adresse = adresse
                    majBandeau.visible = true
                }
            }
        }

        // Zone de contenu (couleurs "contenu" de Plasma)
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Kirigami.Theme.colorSet: Kirigami.Theme.View
            Kirigami.Theme.inherit: false
            color: Kirigami.Theme.backgroundColor

            // seitenleiste : Schnellzugriff (angeheftete Ordner) und Baum « Dieser PC » wie im Windows-Explorer
            Rectangle {
                id: sidebar
                visible: win.quickShown
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: visible ? win.sideWidth : 0
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.04)
                Kirigami.Separator { anchors.right: parent.right; height: parent.height }

                DropArea {   // Ordner aus Dolphin hineinziehen heftet sie an
                    anchors.fill: parent
                    keys: ["text/uri-list"]
                    onDropped: function(drop) {
                        for (var i = 0; i < drop.urls.length; i++)
                            backend.pinPath(drop.urls[i].toString(), "", "")
                    }
                }
                // Ein gemeinsames Rechtsklick-Menü für alle Zeilen (wirkt auf rowMenu.t)
                QQC2.Menu {
                    id: rowMenu
                    property var t: ({})
                    readonly property bool isPin: t.type === "pin"
                    QQC2.MenuItem {
                        text: win.trad("Open")
                        icon.name: "folder-open"
                        onTriggered: backend.openFolder(rowMenu.t.path)
                    }
                    QQC2.MenuItem {
                        text: win.trad("Open in terminal")
                        icon.name: "utilities-terminal"
                        onTriggered: backend.openTerminal(rowMenu.t.path)
                    }
                    QQC2.MenuItem {
                        text: win.trad("Copy path")
                        icon.name: "edit-copy"
                        onTriggered: backend.copyPath(rowMenu.t.path)
                    }
                    QQC2.MenuSeparator {}
                    QQC2.MenuItem {
                        text: win.trad("Move up")
                        icon.name: "go-up"
                        visible: rowMenu.isPin
                        height: visible ? implicitHeight : 0
                        enabled: rowMenu.t.pinIndex > 0
                        onTriggered: backend.movePin(rowMenu.t.path, -1)
                    }
                    QQC2.MenuItem {
                        text: win.trad("Move down")
                        icon.name: "go-down"
                        visible: rowMenu.isPin
                        height: visible ? implicitHeight : 0
                        enabled: rowMenu.t.pinIndex < rowMenu.t.pinCount - 1
                        onTriggered: backend.movePin(rowMenu.t.path, 1)
                    }
                    QQC2.MenuItem {
                        text: win.isPinned(rowMenu.t.path || "") ? win.trad("Unpin from Quick access")
                                                                 : win.trad("Pin to Quick access")
                        icon.name: win.isPinned(rowMenu.t.path || "") ? "window-unpin" : "window-pin"
                        onTriggered: win.isPinned(rowMenu.t.path) ? backend.unpinPath(rowMenu.t.path)
                                                                  : backend.pinPath(rowMenu.t.path, rowMenu.t.label, rowMenu.t.icon)
                    }
                }

                ListView {
                    id: sideList
                    objectName: "sideList"
                    anchors.fill: parent
                    anchors.rightMargin: 1
                    clip: true
                    model: win.sidebarRows
                    spacing: 1
                    QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
                    displaced: Transition { NumberAnimation { properties: "y"; duration: 160; easing.type: Easing.OutCubic } }
                    delegate: Item {
                        id: row
                        readonly property var r: modelData
                        readonly property bool isHead: r.type === "head"
                        readonly property bool isNode: r.type === "node"
                        readonly property bool isPinRow: r.type === "pin"
                        readonly property bool pinned: (isNode || isPinRow) && win.isPinned(r.path)
                        readonly property string selKey: r.type + ":" + (r.path || "")
                        readonly property bool selected: (isNode || isPinRow) && win.sideSelKey === selKey
                        width: ListView.view.width
                        height: isHead ? 38 : (r.type === "hint" ? 54 : 30)
                        opacity: (isPinRow && r.exists === false) ? 0.5 : 1.0

                        // Hover über die GANZE Zeile : ein HoverHandler hängt nicht davon ab, welches Kind (Beschriftung, Symbol …) unter der
                        // Maus liegt ; die Beschriftung fängt Hover-Ereignisse selbst ab, eine MouseArea darunter bekäme sie nicht.
                        HoverHandler { id: rowHover }
                        Rectangle {   // Hover und Auswahl
                            anchors.fill: parent
                            anchors.leftMargin: 6
                            anchors.rightMargin: 6
                            radius: 6
                            visible: !row.isHead && r.type !== "hint"
                            opacity: (rowHover.hovered || rowMouse.pressed || row.selected) ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: 120 } }
                            color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                           Kirigami.Theme.highlightColor.b, (row.selected || rowMouse.pressed) ? 0.24 : 0.14)
                            border.width: row.selected ? 1 : 0
                            border.color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                           Kirigami.Theme.highlightColor.b, 0.7)
                        }
                        // Hierarchielinien : eine dünne senkrechte Linie je Ebene
                        Repeater {
                            model: row.isNode ? r.depth : 0
                            delegate: Rectangle {
                                x: 21 + index * 16
                                width: 1
                                height: row.height + 1
                                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.14)
                            }
                        }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: row.isHead ? 12 : (row.isNode ? 14 + r.depth * 16 : 16)
                            anchors.rightMargin: 12
                            spacing: row.isHead ? 6 : 7
                            visible: r.type !== "hint"
                            Item {   // Auf-/Zuklapper (wie [+]/[−] im klassischen Baum)
                                visible: row.isHead || row.isNode
                                Layout.preferredWidth: 14; Layout.preferredHeight: 14
                                Kirigami.Icon {
                                    anchors.fill: parent
                                    visible: row.isHead || (row.isNode && r.expandable)
                                    source: (row.isHead ? r.collapsed : !r.open) ? "arrow-right" : "arrow-down"
                                    opacity: 0.7
                                    rotation: 0
                                }
                                QQC2.BusyIndicator {
                                    anchors.fill: parent
                                    running: row.isNode && r.loading
                                    visible: running
                                }
                            }
                            Kirigami.Icon {
                                source: r.icon || "folder"
                                Layout.preferredWidth: row.isHead ? 16 : 18
                                Layout.preferredHeight: row.isHead ? 16 : 18
                                color: (row.isHead && r.key === "quick") ? Kirigami.Theme.highlightColor : "transparent"
                                isMask: row.isHead && r.key === "quick"
                            }
                            QQC2.Label {
                                text: r.label || ""
                                font.weight: row.isHead ? Font.DemiBold : Font.Normal
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                            QQC2.ToolButton {   // « + » : Ordner per Dialog anheften
                                visible: row.isHead && r.canAdd === true
                                icon.name: "list-add"
                                icon.width: 14; icon.height: 14
                                implicitWidth: 26; implicitHeight: 26
                                QQC2.ToolTip.visible: hovered
                                QQC2.ToolTip.delay: 400
                                QQC2.ToolTip.text: win.trad("Pin a folder…")
                                onClicked: pinDialog.open()
                            }
                            Kirigami.Icon {   // Pin-Symbol : angeheftet = sichtbar, sonst nur beim Überfahren ; Klick schaltet um
                                visible: row.isNode || row.isPinRow
                                source: (row.pinned !== pinGlyphMouse.containsMouse) ? "window-pin" : "window-unpin"   // zeigt beim Überfahren das Ergebnis des Klicks
                                Layout.preferredWidth: 13; Layout.preferredHeight: 13
                                opacity: pinGlyphMouse.containsMouse ? 1.0
                                       : (row.pinned ? 0.55 : (rowHover.hovered ? 0.35 : 0.0))
                                Behavior on opacity { NumberAnimation { duration: 120 } }
                                MouseArea {
                                    id: pinGlyphMouse
                                    anchors.fill: parent
                                    anchors.margins: -6
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: row.pinned ? backend.unpinPath(r.path) : backend.pinPath(r.path, r.label, r.icon)
                                }
                            }
                        }
                        QQC2.Label {   // leere Schnellzugriff-Liste : Hinweis
                            anchors.centerIn: parent
                            width: parent.width - 40
                            visible: r.type === "hint"
                            text: win.trad("Drag folders here to pin them")
                            opacity: 0.55
                            wrapMode: Text.Wrap
                            horizontalAlignment: Text.AlignHCenter
                        }
                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            z: -1
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onPressed: if (row.isNode || row.isPinRow) win.sideSelKey = row.selKey
                            onClicked: function(mouse) {
                                if (row.isHead) {
                                    if (r.key === "quick") win.quickCollapsed = !win.quickCollapsed
                                    else win.pcCollapsed = !win.pcCollapsed
                                } else if (mouse.button === Qt.RightButton && r.path) {
                                    rowMenu.t = r
                                    rowMenu.popup()
                                } else if (row.isNode) {
                                    win.toggleNode(r.path)   // Klick klappt auf/zu
                                } else if (row.isPinRow) {
                                    backend.openFolder(r.path)
                                }
                            }
                            onDoubleClicked: function(mouse) {
                                if (row.isNode && mouse.button === Qt.LeftButton)
                                    backend.openFolder(r.path)   // Doppelklick öffnet in Dolphin
                            }
                        }
                        QQC2.ToolTip.visible: rowHover.hovered && !!r.path
                        QQC2.ToolTip.delay: 700
                        QQC2.ToolTip.text: (isPinRow && r.exists === false) ? win.trad("Folder not found") : (r.path || "")
                    }
                }
            }
            FolderDialog {
                id: pinDialog
                title: win.trad("Pin a folder…")
                onAccepted: backend.pinPath(selectedFolder.toString(), "", "")
            }

            QQC2.ScrollView {
                id: scroll
                anchors.left: sidebar.right
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                contentWidth: availableWidth

                ColumnLayout {
                    x: 10
                    width: scroll.availableWidth - 10
                    spacing: 0

                    // En-tête de rubrique "Dossiers"
                    Item {
                        visible: win.foldersShown
                        Layout.fillWidth: true
                        Layout.leftMargin: 23
                        Layout.rightMargin: 15
                        Layout.topMargin: 12
                        Layout.bottomMargin: 4
                        implicitHeight: headerRow.implicitHeight

                        RowLayout {
                            id: headerRow
                            anchors.fill: parent
                            spacing: 4

                            Kirigami.Icon {
                                source: win.foldersCollapsed ? "arrow-up" : "arrow-down"
                                Layout.preferredWidth: 14
                                Layout.preferredHeight: 14
                            }
                            QQC2.Label {
                                text: win.trad("Folders ({n})").replace("{n}", foldersModel.length)
                                opacity: 0.75
                                Layout.rightMargin: 6
                            }
                            Kirigami.Separator { Layout.fillWidth: true }
                        }
                        MouseArea {   // flecheSeule : seule la flèche replie la rubrique
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: 24
                            cursorShape: Qt.PointingHandCursor
                            onClicked: win.foldersCollapsed = !win.foldersCollapsed
                        }
                    }

                    // Grille des dossiers
                    GridLayout {
                        id: folderGrid
                        visible: win.foldersShown && !win.foldersCollapsed
                        Layout.fillWidth: true
                        Layout.leftMargin: 15
                        Layout.rightMargin: 15
                        Layout.bottomMargin: 8
                        readonly property real cellWidth: Math.max(216, frameWidth)
                        columns: Math.max(1, Math.floor((scroll.availableWidth - 32) / (cellWidth + 8)))
                        columnSpacing: 8
                        rowSpacing: 6
                        uniformCellWidths: true

                        // cadreDossiers : largeur du cadre = marge + icône + espace + nom le plus long + marge
                        TextMetrics {
                            id: folderLongest
                            font: Kirigami.Theme.defaultFont
                            text: {
                                var m = ""
                                for (var i = 0; i < foldersModel.length; i++)
                                    if (foldersModel[i].label.length > m.length)
                                        m = foldersModel[i].label
                                return m
                            }
                        }
                        readonly property real frameWidth: 8 + 67 + 10 + Math.ceil(folderLongest.advanceWidth) + 16

                        Repeater {
                            model: foldersModel
                            delegate: Item {
                                Layout.fillWidth: false
                                Layout.preferredWidth: folderGrid.cellWidth
                                Layout.preferredHeight: 80

                                Row {
                                    anchors.left: parent.left
                                    anchors.leftMargin: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 10

                                    Kirigami.Icon {
                                        source: modelData.icon
                                        width: 67; height: 67
                                    }
                                    QQC2.Label {
                                        text: modelData.label
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                // Cadre au survol (comme Dolphin) : couleur d'accent de Plasma, translucide
                                Rectangle {
                                    z: -1
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    width: Math.min(parent.width, folderGrid.frameWidth)
                                    radius: 5
                                    visible: folderMouse.containsMouse || folderMouse.pressed
                                    color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                                   Kirigami.Theme.highlightColor.b, 0.12)
                                    border.width: 1
                                    border.color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                                          Kirigami.Theme.highlightColor.b, 0.35)
                                }
                                MouseArea {
                                    id: folderMouse
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    width: Math.min(parent.width, folderGrid.frameWidth)
                                    hoverEnabled: true
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onPressed: win.selectedKey = ""
                                    onDoubleClicked: backend.openFolder(modelData.path)
                                    onClicked: function(mouse) {
                                        if (mouse.button === Qt.RightButton)
                                            folderMenu.popup()
                                    }
                                }
                                QQC2.Menu {
                                    id: folderMenu
                                    QQC2.MenuItem {
                                        text: win.trad("Open")
                                        icon.name: "folder-open"
                                        onTriggered: backend.openFolder(modelData.path)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Open in terminal")
                                        icon.name: "utilities-terminal"
                                        onTriggered: backend.openTerminal(modelData.path)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Copy path")
                                        icon.name: "edit-copy"
                                        onTriggered: backend.copyPath(modelData.path)
                                    }
                                    QQC2.MenuSeparator {}
                                    QQC2.MenuItem {
                                        text: win.isPinned(modelData.path) ? win.trad("Unpin from Quick access")
                                                                           : win.trad("Pin to Quick access")
                                        icon.name: win.isPinned(modelData.path) ? "window-unpin" : "window-pin"
                                        onTriggered: win.isPinned(modelData.path) ? backend.unpinPath(modelData.path)
                                                                                  : backend.pinPath(modelData.path, modelData.label, modelData.icon)
                                    }
                                }
                            }
                        }
                    }

                    // En-tête de rubrique "Périphériques et lecteurs"
                    Item {
                        visible: win.disksShown
                        Layout.fillWidth: true
                        Layout.leftMargin: 23
                        Layout.rightMargin: 15
                        Layout.topMargin: 12
                        Layout.bottomMargin: 4
                        implicitHeight: disksHeaderRow.implicitHeight

                        RowLayout {
                            id: disksHeaderRow
                            anchors.fill: parent
                            spacing: 4

                            Kirigami.Icon {
                                source: win.disksCollapsed ? "arrow-up" : "arrow-down"
                                Layout.preferredWidth: 14
                                Layout.preferredHeight: 14
                            }
                            QQC2.Label {
                                text: win.trad("Devices and drives ({n})").replace("{n}", backend.disks.length)
                                opacity: 0.75
                                Layout.rightMargin: 6
                            }
                            Kirigami.Separator { Layout.fillWidth: true }
                        }
                        MouseArea {   // flecheSeule : seule la flèche replie la rubrique
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: 24
                            cursorShape: Qt.PointingHandCursor
                            onClicked: win.disksCollapsed = !win.disksCollapsed
                        }
                    }

                    // Cartes des disques
                    GridLayout {
                        visible: win.disksShown && !win.disksCollapsed
                        Layout.fillWidth: true
                        Layout.leftMargin: 15
                        Layout.rightMargin: 15
                        Layout.topMargin: 16
                        Layout.bottomMargin: 8
                        columns: win.cardCols
                        columnSpacing: 8
                        rowSpacing: 8
                        uniformCellWidths: true

                        Repeater {
                            model: backend.disks
                            delegate: Item {
                                Layout.fillWidth: false
                                Layout.preferredWidth: win.cardWidth
                                Layout.preferredHeight: 88
                                property real frac: modelData.total > 0 ? modelData.used / modelData.total : 0

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 10

                                    Item {
                                        Layout.preferredWidth: 48
                                        Layout.preferredHeight: 48
                                        Layout.alignment: Qt.AlignVCenter
                                        Kirigami.Icon {
                                            anchors.centerIn: parent
                                            source: modelData.icon
                                            scale: cardMouse.containsMouse ? 1.08 : 1.0
                                            Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                                            width: modelData.isKey ? 40 : 48
                                            height: width
                                        }
                                        // santeDisque (1.1) : pastille orange (usure) ou rouge (défaillant)
                                        Image {
                                            readonly property string src: modelData.health ? (badgeHealth[modelData.health] || "") : ""
                                            visible: src !== ""
                                            source: src
                                            width: 20; height: 20
                                            sourceSize.width: 80
                                            sourceSize.height: 80
                                            smooth: true
                                            mipmap: true
                                            anchors.right: parent.right
                                            anchors.bottom: parent.bottom
                                            anchors.rightMargin: -2
                                            anchors.bottomMargin: -2
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.alignment: Qt.AlignVCenter
                                        spacing: 5

                                        RowLayout {   // texteLecteur : Name und Temperatur-Chip
                                            Layout.fillWidth: true
                                            Layout.bottomMargin: 2
                                            spacing: 6
                                            QQC2.Label { text: modelData.label; Layout.fillWidth: true; elide: Text.ElideRight }
                                            // festplattenTemperatur : Chip, nur wenn ein Sensor einen Wert liefert (NVMe, SATA mit drivetemp, SMART über udisks)
                                            Rectangle {
                                                id: tempChip
                                                readonly property var t: backend.temps[modelData.device]
                                                readonly property color tone: t === undefined ? "transparent"
                                                        : (t.level === "hot" ? win.gaugeRed : (t.level === "warn" ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.textColor))
                                                visible: t !== undefined
                                                radius: height / 2
                                                implicitHeight: tempText.implicitHeight + 2
                                                implicitWidth: tempText.implicitWidth + 12
                                                color: Qt.rgba(tone.r, tone.g, tone.b, t !== undefined && t.level !== "ok" ? 0.16 : 0.08)
                                                border.width: 1
                                                border.color: Qt.rgba(tone.r, tone.g, tone.b, t !== undefined && t.level !== "ok" ? 0.55 : 0.25)
                                                Behavior on color { ColorAnimation { duration: 300 } }
                                                QQC2.Label {
                                                    id: tempText
                                                    anchors.centerIn: parent
                                                    text: tempChip.t !== undefined ? Math.round(tempChip.t.c) + " °C" : ""
                                                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                                                    font.weight: Font.DemiBold
                                                    color: tempChip.tone
                                                }
                                                HoverHandler { id: tempHover }
                                                QQC2.ToolTip.visible: tempHover.hovered
                                                QQC2.ToolTip.delay: 300
                                                QQC2.ToolTip.text: tempChip.t !== undefined ? win.trad("Temperature") + ": " + tempChip.t.c.toFixed(1).replace(".", trDecimal) + " °C" : ""
                                            }
                                        }

                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 10
                                            visible: !(modelData.isOptical === true && modelData.total === 0) && modelData.isUnmounted !== true
                                            // jaugeGrise : fond de jauge gris clair (16 % de la couleur du texte sur le fond)
                                            color: Qt.tint(Kirigami.Theme.backgroundColor,
                                                           Qt.rgba(Kirigami.Theme.textColor.r,
                                                                   Kirigami.Theme.textColor.g,
                                                                   Kirigami.Theme.textColor.b, 0.16))
                                            radius: height / 2
                                            Rectangle {
                                                property real shownFrac: 0
                                                readonly property real target: frac
                                                onTargetChanged: shownFrac = target
                                                Component.onCompleted: shownFrac = target
                                                Behavior on shownFrac { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                                                Behavior on color { ColorAnimation { duration: 300 } }
                                                width: parent.width * shownFrac
                                                height: parent.height
                                                radius: height / 2
                                                color: (frac < win.alertFrac || modelData.isOptical === true) ? win.gaugeBlue
                                                                  : win.gaugeRed
                                            }
                                        }

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 6
                                            QQC2.Label {
                                                text: modelData.freeText
                                                font: Kirigami.Theme.smallFont
                                                opacity: 0.75
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }
                                            // fastVoll : Warn-Badge ab der einstellbaren Schwelle (win.alertFrac)
                                            Rectangle {
                                                id: warnPill
                                                visible: modelData.total > 0 && modelData.isOptical !== true
                                                         && modelData.isUnmounted !== true && frac >= win.alertFrac
                                                radius: height / 2
                                                implicitHeight: pillText.implicitHeight + 2
                                                implicitWidth: pillText.implicitWidth + 12
                                                color: Qt.rgba(win.gaugeRed.r, win.gaugeRed.g, win.gaugeRed.b, 0.16)
                                                border.width: 1
                                                border.color: Qt.rgba(win.gaugeRed.r, win.gaugeRed.g, win.gaugeRed.b, 0.55)
                                                QQC2.Label {
                                                    id: pillText
                                                    anchors.centerIn: parent
                                                    text: "\u26A0 " + Math.round(frac * 100) + " %"
                                                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                                                    font.weight: Font.DemiBold
                                                    color: win.gaugeRed
                                                }
                                                HoverHandler { id: pillHover }
                                                QQC2.ToolTip.visible: pillHover.hovered
                                                QQC2.ToolTip.delay: 300
                                                QQC2.ToolTip.text: win.trad("Almost full")
                                            }
                                        }
                                        QQC2.Label {   // santeDisque (1.1)
                                            visible: text !== ""
                                            text: modelData.healthText || ""
                                            font.pointSize: Kirigami.Theme.smallFont.pointSize
                                            font.weight: Font.DemiBold
                                            color: modelData.health === "fail" ? "#c42b1c" : "#d35400"
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                    }

                                    // ioVerlauf : Lese-/Schreib-Sparkline der letzten 60 s ; Tooltip mit den Momentanwerten
                                    Item {
                                        id: ioBox
                                        readonly property var io: backend.ioStats[modelData.device]
                                        readonly property real peak: io ? Math.max(1048576, Math.max.apply(null, io.read.concat(io.write))) : 1048576
                                        function pts(serie) {
                                            var n = serie.length, out = [], step = width / 59
                                            for (var i = 0; i < n; i++)
                                                out.push(Qt.point(width - (n - 1 - i) * step, height - 1 - (height - 3) * serie[i] / peak))
                                            return out
                                        }
                                        visible: io !== undefined && modelData.isUnmounted !== true && modelData.isOptical !== true
                                        Layout.preferredWidth: 72
                                        Layout.preferredHeight: 32
                                        Layout.alignment: Qt.AlignVCenter
                                        opacity: ioHover.hovered ? 1.0 : 0.8
                                        Behavior on opacity { NumberAnimation { duration: 140 } }
                                        Rectangle {
                                            anchors.fill: parent
                                            radius: 6
                                            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.05)
                                        }
                                        Shape {
                                            anchors.fill: parent
                                            preferredRendererType: Shape.CurveRenderer
                                            ShapePath {
                                                strokeColor: Kirigami.Theme.positiveTextColor
                                                strokeWidth: 1.5; fillColor: "transparent"; joinStyle: ShapePath.RoundJoin
                                                PathPolyline { path: ioBox.io ? ioBox.pts(ioBox.io.read) : [] }
                                            }
                                            ShapePath {
                                                strokeColor: Kirigami.Theme.neutralTextColor
                                                strokeWidth: 1.5; fillColor: "transparent"; joinStyle: ShapePath.RoundJoin
                                                PathPolyline { path: ioBox.io ? ioBox.pts(ioBox.io.write) : [] }
                                            }
                                        }
                                        HoverHandler { id: ioHover }
                                        QQC2.ToolTip.visible: ioHover.hovered && ioBox.io !== undefined
                                        QQC2.ToolTip.delay: 300
                                        QQC2.ToolTip.text: ioBox.io ? ("\u25BC " + win.rateText(ioBox.io.readRate) + "   \u25B2 " + win.rateText(ioBox.io.writeRate)) : ""
                                    }
                                }
                                // Fin cadre au survol ; au clic, fond teinté de la couleur d'accent (reste jusqu'à un autre clic)
                                Rectangle {
                                    z: -1
                                    anchors.fill: parent
                                    radius: 8
                                    readonly property bool selected: win.selectedKey === modelData.mountpoint
                                    opacity: (selected || cardMouse.containsMouse) ? 1 : 0
                                    Behavior on opacity { NumberAnimation { duration: 140 } }
                                    color: (selected || cardMouse.pressed)
                                           ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.20)
                                           : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.06)
                                    Behavior on color { ColorAnimation { duration: 140 } }
                                    border.width: 1
                                    border.color: selected ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.75)
                                                            : Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.30)
                                    Rectangle {   // Akzentstreifen der Auswahl
                                        width: 3; radius: 1.5
                                        height: parent.height - 24
                                        anchors.left: parent.left; anchors.leftMargin: 3
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: Kirigami.Theme.highlightColor
                                        opacity: parent.selected ? 1 : 0
                                        Behavior on opacity { NumberAnimation { duration: 140 } }
                                    }
                                }
                                MouseArea {
                                    id: cardMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onPressed: {
                                        win.selectedKey = modelData.mountpoint
                                        keyHandler.forceActiveFocus()
                                    }
                                    onDoubleClicked: function(mouse) {
                                        if (mouse.button === Qt.LeftButton)
                                            backend.openFolder(modelData.mountpoint)
                                    }
                                    onClicked: function(mouse) {
                                        if (mouse.button === Qt.RightButton)
                                            diskMenu.popup()
                                    }
                                }
                                QQC2.Menu {
                                    id: diskMenu
                                    QQC2.MenuItem {
                                        text: win.trad("Open with Dolphin")
                                        icon.name: "folder-open"
                                        onTriggered: backend.openFolder(modelData.mountpoint)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Mount")
                                        icon.name: "media-mount"
                                        visible: modelData.isUnmounted === true
                                        height: visible ? implicitHeight : 0
                                        onTriggered: backend.mountDevice(modelData.device)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Open in terminal")
                                        icon.name: "utilities-terminal"
                                        visible: modelData.mountpoint.charAt(0) === "/"
                                        height: visible ? implicitHeight : 0
                                        onTriggered: backend.openTerminal(modelData.mountpoint)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Copy path")
                                        icon.name: "edit-copy"
                                        visible: modelData.mountpoint.charAt(0) === "/"
                                        height: visible ? implicitHeight : 0
                                        onTriggered: backend.copyPath(modelData.mountpoint)
                                    }
                                    QQC2.MenuItem {
                                        visible: modelData.mountpoint.charAt(0) === "/"
                                        height: visible ? implicitHeight : 0
                                        text: win.isPinned(modelData.mountpoint) ? win.trad("Unpin from Quick access")
                                                                                 : win.trad("Pin to Quick access")
                                        icon.name: win.isPinned(modelData.mountpoint) ? "window-unpin" : "window-pin"
                                        onTriggered: win.isPinned(modelData.mountpoint) ? backend.unpinPath(modelData.mountpoint)
                                                                                        : backend.pinPath(modelData.mountpoint, modelData.label, "drive-harddisk")
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Safely remove")
                                        icon.name: "media-eject"
                                        visible: modelData.isUsb && modelData.isUnmounted !== true
                                        height: visible ? implicitHeight : 0
                                        onTriggered: backend.ejectDevice(modelData.device, modelData.label)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Eject")
                                        icon.name: "media-eject"
                                        visible: modelData.isOptical === true
                                        height: visible ? implicitHeight : 0
                                        onTriggered: backend.ejectOptical(modelData.device)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Properties")
                                        icon.name: "document-properties"
                                        visible: modelData.isUnmounted !== true
                                        height: visible ? implicitHeight : 0
                                        onTriggered: win.showProps(modelData)
                                    }
                                }
                            }
                        }
                    }

                    // En-tête de rubrique "Emplacements réseau"
                    Item {
                        visible: win.netShown
                        Layout.fillWidth: true
                        Layout.leftMargin: 23
                        Layout.rightMargin: 15
                        Layout.topMargin: 12
                        Layout.bottomMargin: 4
                        implicitHeight: netHeaderRow.implicitHeight

                        RowLayout {
                            id: netHeaderRow
                            anchors.fill: parent
                            spacing: 4

                            Kirigami.Icon {
                                source: win.netCollapsed ? "arrow-up" : "arrow-down"
                                Layout.preferredWidth: 14
                                Layout.preferredHeight: 14
                            }
                            QQC2.Label {
                                text: win.trad("Network locations ({n})").replace("{n}", backend.networks.length)
                                opacity: 0.75
                                Layout.rightMargin: 6
                            }
                            Kirigami.Separator { Layout.fillWidth: true }
                        }
                        MouseArea {   // flecheSeule : seule la flèche replie la rubrique
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: 24
                            cursorShape: Qt.PointingHandCursor
                            onClicked: win.netCollapsed = !win.netCollapsed
                        }
                    }

                    // Cartes des emplacements réseau : partages montés et emplacements ajoutés par l'utilisateur
                    GridLayout {
                        visible: win.netShown && !win.netCollapsed
                        Layout.fillWidth: true
                        Layout.leftMargin: 15
                        Layout.rightMargin: 15
                        Layout.bottomMargin: 8
                        columns: win.cardCols
                        columnSpacing: 8
                        rowSpacing: 8
                        uniformCellWidths: true

                        Repeater {
                            model: backend.networks
                            delegate: Item {
                                Layout.fillWidth: false
                                Layout.preferredWidth: win.cardWidth
                                Layout.preferredHeight: 88
                                property real frac: modelData.total > 0 ? modelData.used / modelData.total : 0
                                readonly property bool offline: modelData.available === false

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 10

                                    Item {
                                        Layout.preferredWidth: 48
                                        Layout.preferredHeight: 48
                                        Layout.alignment: Qt.AlignVCenter
                                        Kirigami.Icon {
                                            anchors.centerIn: parent
                                            source: modelData.icon
                                            scale: cardMouse.containsMouse ? 1.08 : 1.0
                                            Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                                            width: 48
                                            height: 48
                                            opacity: offline ? 0.4 : 1.0
                                        }
                                        // Pastille rouge : serveur non joignable
                                        // pastilleSvg : image vectorielle nette
                                        Image {
                                            visible: offline && badgeOffline !== ""
                                            source: badgeOffline
                                            width: 20; height: 20
                                            sourceSize.width: 80
                                            sourceSize.height: 80
                                            smooth: true
                                            mipmap: true
                                            anchors.right: parent.right
                                            anchors.bottom: parent.bottom
                                            anchors.rightMargin: -2
                                            anchors.bottomMargin: -2
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.alignment: Qt.AlignVCenter
                                        spacing: 5

                                        QQC2.Label {
                                            text: modelData.label
                                            Layout.bottomMargin: 2
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                            opacity: offline ? 0.6 : 1.0
                                        }

                                        Rectangle {
                                            visible: modelData.total > 0
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 10
                                            // jaugeGrise : fond de jauge gris clair (16 % de la couleur du texte sur le fond)
                                            color: Qt.tint(Kirigami.Theme.backgroundColor,
                                                           Qt.rgba(Kirigami.Theme.textColor.r,
                                                                   Kirigami.Theme.textColor.g,
                                                                   Kirigami.Theme.textColor.b, 0.16))
                                            radius: height / 2
                                            Rectangle {
                                                property real shownFrac: 0
                                                readonly property real target: frac
                                                onTargetChanged: shownFrac = target
                                                Component.onCompleted: shownFrac = target
                                                Behavior on shownFrac { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                                                Behavior on color { ColorAnimation { duration: 300 } }
                                                width: parent.width * shownFrac
                                                height: parent.height
                                                radius: height / 2
                                                color: (frac < win.alertFrac || modelData.isOptical === true) ? win.gaugeBlue
                                                                  : win.gaugeRed
                                            }
                                        }

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 6
                                            QQC2.Label {
                                                text: modelData.freeText
                                                font: Kirigami.Theme.smallFont
                                                opacity: offline ? 0.6 : 0.75
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }
                                            // fastVoll : Warn-Badge ab der einstellbaren Schwelle (win.alertFrac)
                                            Rectangle {
                                                id: warnPill
                                                visible: modelData.total > 0 && modelData.isOptical !== true
                                                         && modelData.isUnmounted !== true && !offline && frac >= win.alertFrac
                                                radius: height / 2
                                                implicitHeight: pillText.implicitHeight + 2
                                                implicitWidth: pillText.implicitWidth + 12
                                                color: Qt.rgba(win.gaugeRed.r, win.gaugeRed.g, win.gaugeRed.b, 0.16)
                                                border.width: 1
                                                border.color: Qt.rgba(win.gaugeRed.r, win.gaugeRed.g, win.gaugeRed.b, 0.55)
                                                QQC2.Label {
                                                    id: pillText
                                                    anchors.centerIn: parent
                                                    text: "\u26A0 " + Math.round(frac * 100) + " %"
                                                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                                                    font.weight: Font.DemiBold
                                                    color: win.gaugeRed
                                                }
                                                HoverHandler { id: pillHover }
                                                QQC2.ToolTip.visible: pillHover.hovered
                                                QQC2.ToolTip.delay: 300
                                                QQC2.ToolTip.text: win.trad("Almost full")
                                            }
                                        }
                                    }
                                }

                                // Fin cadre au survol ; au clic, fond teinté de la couleur d'accent (reste jusqu'à un autre clic)
                                Rectangle {
                                    z: -1
                                    anchors.fill: parent
                                    radius: 8
                                    readonly property bool selected: win.selectedKey === modelData.mountpoint
                                    opacity: (selected || cardMouse.containsMouse) ? 1 : 0
                                    Behavior on opacity { NumberAnimation { duration: 140 } }
                                    color: (selected || cardMouse.pressed)
                                           ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.20)
                                           : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.06)
                                    Behavior on color { ColorAnimation { duration: 140 } }
                                    border.width: 1
                                    border.color: selected ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.75)
                                                            : Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.30)
                                    Rectangle {   // Akzentstreifen der Auswahl
                                        width: 3; radius: 1.5
                                        height: parent.height - 24
                                        anchors.left: parent.left; anchors.leftMargin: 3
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: Kirigami.Theme.highlightColor
                                        opacity: parent.selected ? 1 : 0
                                        Behavior on opacity { NumberAnimation { duration: 140 } }
                                    }
                                }
                                MouseArea {
                                    id: cardMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onPressed: {
                                        win.selectedKey = modelData.mountpoint
                                        keyHandler.forceActiveFocus()
                                    }
                                    onDoubleClicked: function(mouse) {
                                        if (mouse.button !== Qt.LeftButton)
                                            return
                                        if (offline) {
                                            msgDialog.title = win.trad("Location unavailable")
                                            msgLabel.text = win.trad("“{name}” is not responding. Check that it is turned on and connected to the network.").replace("{name}", modelData.label)
                                            msgDialog.open()
                                        } else {
                                            backend.openFolder(modelData.mountpoint)
                                        }
                                    }
                                    onClicked: function(mouse) {
                                        if (mouse.button === Qt.RightButton)
                                            netMenu.popup()
                                    }
                                }
                                QQC2.Menu {
                                    id: netMenu
                                    QQC2.MenuItem {
                                        text: win.trad("Open with Dolphin")
                                        icon.name: "folder-open"
                                        enabled: !offline
                                        onTriggered: backend.openFolder(modelData.mountpoint)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Properties")
                                        icon.name: "document-properties"
                                        visible: modelData.mounted === true || modelData.total > 0
                                        height: visible ? implicitHeight : 0
                                        onTriggered: win.showProps(modelData)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Open in terminal")
                                        icon.name: "utilities-terminal"
                                        visible: modelData.mounted === true && modelData.mountpoint.charAt(0) === "/"
                                        height: visible ? implicitHeight : 0
                                        onTriggered: backend.openTerminal(modelData.mountpoint)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Copy path")
                                        icon.name: "edit-copy"
                                        onTriggered: backend.copyPath(modelData.mountpoint)
                                    }
                                    QQC2.MenuItem {
                                        visible: modelData.mountpoint.charAt(0) === "/"
                                        height: visible ? implicitHeight : 0
                                        text: win.isPinned(modelData.mountpoint) ? win.trad("Unpin from Quick access")
                                                                                 : win.trad("Pin to Quick access")
                                        icon.name: win.isPinned(modelData.mountpoint) ? "window-unpin" : "window-pin"
                                        onTriggered: win.isPinned(modelData.mountpoint) ? backend.unpinPath(modelData.mountpoint)
                                                                                        : backend.pinPath(modelData.mountpoint, modelData.label, "drive-harddisk")
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Disconnect")
                                        icon.name: "network-disconnect"
                                        visible: modelData.mounted === true && modelData.mountpoint.charAt(0) === "/"
                                        height: visible ? implicitHeight : 0
                                        onTriggered: backend.unmountNetwork(modelData.mountpoint)
                                    }
                                    QQC2.MenuItem {
                                        text: win.trad("Remove this location")
                                        icon.name: "list-remove"
                                        visible: modelData.configured === true
                                        height: visible ? implicitHeight : 0
                                        onTriggered: backend.removeNetwork(modelData.url)
                                    }
                                }
                            }
                        }
                    }

                    // Imprimantes et périphériques : information seulement, sous les emplacements réseau
                    Item {
                        visible: win.printersShown && backend.printers.length > 0
                        Layout.fillWidth: true
                        Layout.leftMargin: 23
                        Layout.rightMargin: 15
                        Layout.topMargin: 12
                        Layout.bottomMargin: 4
                        implicitHeight: printersHeaderRow.implicitHeight

                        RowLayout {
                            id: printersHeaderRow
                            anchors.fill: parent
                            spacing: 4

                            Kirigami.Icon {
                                source: win.printersCollapsed ? "arrow-up" : "arrow-down"
                                Layout.preferredWidth: 14
                                Layout.preferredHeight: 14
                            }
                            QQC2.Label {
                                text: win.trad("Printers and devices ({n})").replace("{n}", backend.printers.length)
                                opacity: 0.75
                                Layout.rightMargin: 6
                            }
                            Kirigami.Separator { Layout.fillWidth: true }
                        }
                        MouseArea {   // flecheSeule : seule la flèche replie la rubrique
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: 24
                            cursorShape: Qt.PointingHandCursor
                            onClicked: win.printersCollapsed = !win.printersCollapsed
                        }
                    }

                    GridLayout {
                        visible: win.printersShown && backend.printers.length > 0 && !win.printersCollapsed
                        Layout.fillWidth: true
                        Layout.leftMargin: 15
                        Layout.rightMargin: 15
                        Layout.bottomMargin: 8
                        columns: win.cardCols
                        columnSpacing: 8
                        rowSpacing: 8
                        uniformCellWidths: true

                        Repeater {
                            model: backend.printers
                            delegate: Item {
                                Layout.fillWidth: false
                                Layout.preferredWidth: win.cardWidth
                                Layout.preferredHeight: 72
                                opacity: modelData.offline ? 0.5 : 1.0
                                readonly property string settingsMod: win.settingsModuleFor(modelData)

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 10

                                    Item {
                                        Layout.preferredWidth: 48
                                        Layout.preferredHeight: 48
                                        Layout.alignment: Qt.AlignVCenter
                                        Kirigami.Icon {
                                            anchors.centerIn: parent
                                            source: modelData.icon
                                            scale: printerMouse.containsMouse ? 1.08 : 1.0
                                            Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                                            width: 48
                                            height: 48
                                        }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.alignment: Qt.AlignVCenter
                                        spacing: 3

                                        QQC2.Label {
                                            text: modelData.label
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }
                                        QQC2.Label {
                                            text: modelData.statusText
                                            font: Kirigami.Theme.smallFont
                                            opacity: 0.75
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }
                                    }

                                    // tintenBalken : Füllstand je Patrone als kleines Balkendiagramm direkt auf der Druckerkarte
                                    Item {
                                        id: inkBox
                                        readonly property var inks: modelData.inks || []
                                        visible: inks.length > 0 && modelData.offline !== true
                                        Layout.preferredWidth: inks.length * 9 + Math.max(0, inks.length - 1) * 5
                                        Layout.preferredHeight: 44
                                        Layout.alignment: Qt.AlignVCenter
                                        Row {
                                            spacing: 5
                                            Repeater {
                                                model: inkBox.inks
                                                delegate: Item {
                                                    width: 9
                                                    height: 44
                                                    readonly property bool dark: Qt.colorEqual(modelData.color, "#000000")
                                                    Rectangle {   // Spur
                                                        anchors.fill: parent
                                                        radius: 4
                                                        color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.10)
                                                        border.width: 1
                                                        border.color: modelData.low ? win.gaugeRed
                                                                                     : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.30)
                                                    }
                                                    Rectangle {   // Füllung, wächst von unten
                                                        property real shown: 0
                                                        Component.onCompleted: shown = modelData.level
                                                        Behavior on shown { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                                                        anchors.bottom: parent.bottom
                                                        width: parent.width
                                                        height: Math.max(parent.width, parent.height * shown / 100)
                                                        radius: 4
                                                        visible: modelData.level > 0
                                                        // schwarze Tinte würde auf dunklem Thema verschwinden : dann Textfarbe des Themas
                                                        color: parent.dark ? Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.85)
                                                                           : modelData.color
                                                    }
                                                }
                                            }
                                        }
                                        HoverHandler { id: inkHover }
                                        QQC2.ToolTip.visible: inkHover.hovered
                                        QQC2.ToolTip.delay: 300
                                        QQC2.ToolTip.text: inks.map(function(i) { return i.name + ": " + i.level + " %" }).join("\n")
                                    }
                                }
                                Rectangle {
                                    z: -1
                                    anchors.fill: parent
                                    radius: 4
                                    readonly property bool selected: win.selectedKey === modelData.key
                                    visible: selected || printerMouse.containsMouse
                                    color: (selected || printerMouse.pressed)
                                           ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                                     Kirigami.Theme.highlightColor.b, 0.22)
                                           : "transparent"
                                    border.width: 1
                                    border.color: selected
                                                  ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                                            Kirigami.Theme.highlightColor.b, 0.8)
                                                  : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                                            Kirigami.Theme.textColor.b, 0.55)
                                }
                                MouseArea {
                                    id: printerMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onPressed: win.selectedKey = modelData.key
                                    onDoubleClicked: function(mouse) {
                                        if (mouse.button !== Qt.LeftButton)
                                            return
                                        if (modelData.scanner === true)   // scannersInfo (1.1) : numériser avec Skanpage
                                            backend.launchApp("skanpage")
                                        else if (!modelData.indicator)
                                            win.showPrinter(modelData)
                                        else if (settingsMod !== "" && backend.hasSettings(settingsMod))
                                            backend.openSettings(settingsMod)   // Controller, Maus, Tastatur … -> Systemeinstellungen
                                    }
                                    onClicked: function(mouse) {
                                        if (mouse.button === Qt.RightButton && (!modelData.indicator
                                                || (settingsMod !== "" && backend.hasSettings(settingsMod))))
                                            printerMenu.popup()
                                    }
                                }
                                QQC2.Menu {
                                    id: printerMenu
                                    QQC2.MenuItem {
                                        visible: !modelData.indicator
                                        text: win.trad("Properties")
                                        icon.name: "document-properties"
                                        onTriggered: win.showPrinter(modelData)
                                    }
                                    QQC2.MenuItem {
                                        visible: settingsMod !== "" && backend.hasSettings(settingsMod)
                                        text: win.trad("Open settings")
                                        icon.name: "configure"
                                        onTriggered: backend.openSettings(settingsMod)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // clicVideSelection : un clic à côté d'un disque retire sa sélection.
            // Zone transparente au-dessus du contenu ; elle n'accepte pas le clic, qui continue donc
            // vers l'élément dessous (qui se resélectionne s'il est visé).
            MouseArea {
                z: 10
                anchors.fill: parent
                onPressed: function(mouse) {
                    win.selectedKey = ""
                    keyHandler.forceActiveFocus()
                    mouse.accepted = false
                }
            }
        }

        // Pied de page
        Kirigami.Separator { Layout.fillWidth: true }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 29
            color: Kirigami.Theme.backgroundColor

            QQC2.Label {
                anchors.left: parent.left
                anchors.leftMargin: 15
                anchors.verticalCenter: parent.verticalCenter
                opacity: 0.75
                text: win.trad("{n} item(s)").replace("{n}", (win.foldersCollapsed || !win.foldersShown ? 0 : foldersModel.length) + (win.disksCollapsed || !win.disksShown ? 0 : backend.disks.length) + (win.netCollapsed || !win.netShown ? 0 : backend.networks.length) + (win.printersCollapsed || !win.printersShown ? 0 : backend.printers.length))
            }
        }
    }
}
"""


APP_VERSION = '1.2.0-fork'
APP_AUTEUR = """Original Copyright (C) 2026 naykkalak
Modified and maintained by Christian (2026), with help from his son Leon"""
APP_LICENCE = 'GPL-3.0-or-later'


def about_info():
    """Informations affichées par « À propos de Ce PC »."""
    from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
    icone = os.path.join(ICON_CACHE_DIR, "app-icon.png")
    return {"version": APP_VERSION, "auteur": APP_AUTEUR, "licence": {"GPL-3.0-or-later": tr("GPL-3.0 or later"), "GPL-3.0-only": tr("GPL-3.0 only")}.get(APP_LICENCE, APP_LICENCE),   # licenceTraduite
            "qt": QT_VERSION_STR, "pyqt": PYQT_VERSION_STR,
            "python": "%d.%d.%d" % sys.version_info[:3],
            "icon": ("file://" + icone) if os.path.isfile(icone) else ""}


def bar_icons_ruban():
    """Icônes du mode complet de la barre (rubanWindows) : jeu coloré windows-modern, sinon icône du thème."""
    svg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">\n<path d="M12 4.5C16.1421 4.5 19.5 7.85786 19.5 12C19.5 16.1421 16.1421 19.5 12 19.5C7.85786 19.5 4.5 16.1421 4.5 12C4.5 11.6236 4.52772 11.2538 4.58123 10.8923C4.64845 10.4382 4.31609 10 3.85708 10C3.48623 10 3.161 10.2562 3.10471 10.6228C3.03576 11.0718 3 11.5317 3 12C3 16.9706 7.02944 21 12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C9.69494 3 7.59227 3.86656 6 5.29168V4.25C6 3.83579 5.66421 3.5 5.25 3.5C4.83579 3.5 4.5 3.83579 4.5 4.25V7.25C4.5 7.66421 4.83579 8 5.25 8H8.25C8.66421 8 9 7.66421 9 7.25C9 6.83579 8.66421 6.5 8.25 6.5H6.90093C8.23907 5.25883 10.0309 4.5 12 4.5Z" fill="#1e88e5"/>\n</svg>\n'
    actualiser = ""
    chemin = os.path.join(os.path.expanduser("~/.cache/fenestra"), "ce-pc-actualiser.svg")
    try:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        if not os.path.isfile(chemin) or _lire_texte(chemin) != svg:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(svg)
        actualiser = "file://" + chemin
    except OSError:
        pass
    voulus = (("props", "mimetypes/text-x-generic", "text-x-generic"),
              ("open", "places/folder-open", "folder-open"),
              ("add", "places/folder-network-open", "folder-network"),
              ("settings", "apps/preferences-system", "preferences-system"),
              ("info", "devices/computer", "computer"),
              ("about", "apps/help-about", "help-about"))
    res = {"refresh": actualiser or "view-refresh"}
    for cle, sous, repli in voulus:
        res[cle] = repli
        for base in (os.path.expanduser("~/.local/share/icons/windows-modern"),
                     "/usr/share/icons/windows-modern"):
            p = os.path.join(base, sous + ".svg")
            if os.path.isfile(p):
                res[cle] = "file://" + p
                break
    return res


WIN_CONFIG = os.path.join(CONFIG_DIR, "ce-pc-fenetre.json")   # fenetreMemo


def load_window_state():
    """Dernière taille de la fenêtre : {"w", "h", "max"}. Valeurs à 0 si inconnues ou invalides."""
    etat = {"w": 0, "h": 0, "max": False}
    try:
        with open(WIN_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        w, h = int(data.get("w", 0)), int(data.get("h", 0))
        geo = QApplication.primaryScreen().availableGeometry()
        if 640 <= w <= max(640, geo.width()) and 460 <= h <= max(460, geo.height()):
            etat["w"], etat["h"] = w, h
        etat["max"] = bool(data.get("max", False))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return etat


def instance_existante(nom):
    """True si Ce PC läuft schon (der Aufruf holt dessen Fenster nach vorn)."""
    if QLocalSocket is None:
        return False
    sock = QLocalSocket()
    sock.connectToServer(nom)
    if sock.waitForConnected(300):
        sock.write(b"raise\n")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def serveur_instance(nom, backend):
    """Lokaler Server : jeder weitere Start meldet sich hier und beendet sich dann."""
    if QLocalServer is None:
        return None
    QLocalServer.removeServer(nom)   # alte Socket-Datei nach einem Absturz
    srv = QLocalServer()
    srv.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not srv.listen(nom):
        return None

    def nouveau():
        while srv.hasPendingConnections():
            c = srv.nextPendingConnection()
            c.close()
            c.deleteLater()
            backend.raiseRequested.emit()

    srv.newConnection.connect(nouveau)
    return srv


def main():
    if "--dump-qml" in sys.argv:   # Oberfläche als .qml-Datei ausgeben (Bearbeitung mit Syntaxfarben)
        sys.stdout.write(QML)
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName("fenestra-ce-pc")
    app.setDesktopFileName("fenestra-ce-pc")
    nom_instance = "fenestra-ce-pc-%d" % os.getuid()
    if not os.environ.get("CEPC_MULTI") and instance_existante(nom_instance):
        return 0
    theme = get_icon_theme_name()
    QIcon.setThemeName(theme)

    app_icon = os.path.join(ICON_CACHE_DIR, "app-icon.png")
    if os.path.isfile(app_icon):
        app.setWindowIcon(QIcon(app_icon))

    folders = list_user_folders()
    print(f"[ce_pc_plasma] thème d'icônes : {theme}")
    print("[ce_pc_plasma] icônes dossiers :",
          {f["label"]: f["icon"] for f in folders})

    backend = Backend()
    serveur = None if os.environ.get("CEPC_MULTI") else serveur_instance(nom_instance, backend)   # Referenz halten
    qml = QML
    chemin_qml = os.environ.get("CEPC_QML")   # Entwicklung: QML aus Datei laden (siehe --dump-qml)
    if chemin_qml:
        try:
            with open(chemin_qml, encoding="utf-8") as f:
                qml = f.read()
        except OSError as e:
            print("[ce_pc_plasma] CEPC_QML nicht lesbar :", e)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("foldersModel", folders)
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("trTable", table_traductions(qml))
    engine.rootContext().setContextProperty("trDecimal", DECIMAL)
    engine.rootContext().setContextProperty("barIconsRuban", bar_icons_ruban())
    engine.rootContext().setContextProperty("aboutInfo", about_info())
    engine.rootContext().setContextProperty("sectInit", load_sections())
    engine.rootContext().setContextProperty("winInit", load_window_state())
    engine.rootContext().setContextProperty("badgeOffline", badge_offline())
    engine.rootContext().setContextProperty("badgeHealth", badge_health())
    engine.loadData(qml.encode("utf-8"))
    if not engine.rootObjects():
        print("Échec du chargement QML")
        return 1
    code = app.exec()
    del serveur
    return code


if __name__ == "__main__":
    sys.exit(main())
