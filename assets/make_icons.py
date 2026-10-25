#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Erzeugt die DriveDeck-Symbole in allen Größen aus assets/drivedeck-source.jpg (1024 x 1024).

Das Quellbild ist ein Quadrat ohne Transparenz ; hier bekommt es die abgerundeten Ecken eines App-Symbols und wird für
jede Größe einzeln verkleinert (schrittweise halbiert, das hält die Linien scharf). Ergebnis :
assets/hicolor/<Größe>x<Größe>/apps/drivedeck.png  (wird von install.sh nach ~/.local/share/icons/hicolor kopiert).

    python3 assets/make_icons.py
"""
import os
import sys

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QGuiApplication, QImage, QPainter, QPainterPath

GROESSEN = (16, 22, 24, 32, 48, 64, 128, 256, 512)
ECKEN = 0.225   # Eckenradius als Anteil der Kantenlänge (wie bei den Symbolen von Plasma und Windows 11)

hier = os.path.dirname(os.path.abspath(__file__))
app = QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])

quelle = QImage(os.path.join(hier, "drivedeck-source.jpg")).convertToFormat(QImage.Format.Format_ARGB32)
if quelle.isNull() or quelle.width() != quelle.height():
    sys.exit("drivedeck-source.jpg fehlt oder ist nicht quadratisch")

# Eckenmaske in voller Größe, danach verkleinern
voll = QImage(quelle.size(), QImage.Format.Format_ARGB32)
voll.fill(Qt.GlobalColor.transparent)
p = QPainter(voll)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
pfad = QPainterPath()
r = quelle.width() * ECKEN
pfad.addRoundedRect(QRectF(0, 0, quelle.width(), quelle.height()), r, r)
p.setClipPath(pfad)
p.drawImage(0, 0, quelle)
p.end()


def verkleinern(bild, ziel):
    while bild.width() // 2 >= ziel and bild.width() > ziel:
        bild = bild.scaled(bild.width() // 2, bild.height() // 2, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    return bild.scaled(ziel, ziel, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)


for g in GROESSEN:
    ordner = os.path.join(hier, "hicolor", "%dx%d" % (g, g), "apps")
    os.makedirs(ordner, exist_ok=True)
    verkleinern(voll, g).save(os.path.join(ordner, "drivedeck.png"))
    print("  %3d x %3d" % (g, g))
