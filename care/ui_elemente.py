"""Wiederverwendbare Oberflächen-Bausteine: Karten, Kacheln, Status-Etiketten, Diagramme."""
from __future__ import annotations

import math

from PyQt5.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSizePolicy, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .database import STATUS_AUSGETRETEN, STATUS_AUSTRITT_ANGEMELDET, STATUS_KEIN, STATUS_MITGLIED

# ------------------------------------------------------------------ Farben
GRUEN = "#1f5130"
GRUEN_HELL = "#2f7a4a"
TEXT = "#1d2a22"
GRAU = "#6b766f"
ROT = "#b42318"
GELB = "#b26b00"

STATUS_FARBEN = {
    STATUS_MITGLIED: ("#dff1e4", "#1a6234"),
    STATUS_AUSTRITT_ANGEMELDET: ("#fff0d1", "#8a5300"),
    STATUS_AUSGETRETEN: ("#fde4e2", "#a5281f"),
    STATUS_KEIN: ("#edf0ee", "#56615a"),
}


# ------------------------------------------------------------------ Knöpfe
def knopf(text: str, art: str = "sekundaer", slot=None, tooltip: str | None = None) -> QPushButton:
    """art: primaer | sekundaer | gefahr | link"""
    b = QPushButton(text)
    b.setObjectName(art)
    b.setCursor(Qt.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def karte(rand: int = 16, abstand: int = 10) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("karte")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(rand, rand, rand, rand)
    lay.setSpacing(abstand)
    return f, lay


def abschnitt_titel(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("abschnitt")
    return l


def seiten_kopf(titel: str, untertitel: str, knoepfe: list[QPushButton]) -> tuple[QWidget, QLabel]:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    links = QVBoxLayout()
    links.setSpacing(2)
    t = QLabel(titel)
    t.setObjectName("seitenTitel")
    u = QLabel(untertitel)
    u.setObjectName("seitenUntertitel")
    u.setWordWrap(True)
    links.addWidget(t)
    links.addWidget(u)
    lay.addLayout(links, 1)
    for b in knoepfe:
        lay.addWidget(b, 0, Qt.AlignBottom)
    return w, u


def pille(text: str, bg: str, fg: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:11px; padding:3px 11px; font-weight:600;")
    l.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return l


# ------------------------------------------------------------------ Tabellen
class SortItem(QTableWidgetItem):
    """Tabellenzelle, die nach einem eigenen Schlüssel sortiert (Datum, Zahl)."""

    def __init__(self, text, schluessel=None):
        super().__init__("" if text is None else str(text))
        self.schluessel = schluessel if schluessel is not None else str(text or "").lower()
        self.setFlags(self.flags() & ~Qt.ItemIsEditable)

    def __lt__(self, other):
        a, b = self.schluessel, getattr(other, "schluessel", other.text())
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


class StatusDelegate(QStyledItemDelegate):
    """Zeichnet den Status als farbiges, abgerundetes Etikett."""

    def _font(self, basis: QFont) -> QFont:
        f = QFont(basis)
        f.setPointSizeF(basis.pointSizeF() * 0.92)
        f.setWeight(QFont.DemiBold)
        return f

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        stil = opt.widget.style() if opt.widget else QApplication.style()
        stil.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)
        if not text:
            return
        bg, fg = STATUS_FARBEN.get(text, ("#edf0ee", "#56615a"))
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        f = self._font(opt.font)
        fm = QFontMetrics(f)
        h = fm.height() + 6
        w = fm.horizontalAdvance(text) + 22
        r = QRectF(opt.rect.x() + 8, opt.rect.center().y() - h / 2 + 1, w, h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(r, h / 2, h / 2)
        painter.setPen(QColor(fg))
        painter.setFont(f)
        painter.drawText(r, Qt.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        fm = QFontMetrics(self._font(option.font))
        return QSize(fm.horizontalAdvance(str(index.data() or "")) + 44, max(s.height(), 34))


def neue_tabelle(mehrfachauswahl: bool = False) -> QTableWidget:
    t = QTableWidget()
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.ExtendedSelection if mehrfachauswahl else QAbstractItemView.SingleSelection)
    t.setShowGrid(False)
    t.setAlternatingRowColors(True)
    t.setSortingEnabled(True)
    t.setWordWrap(False)
    t.setFocusPolicy(Qt.StrongFocus if mehrfachauswahl else Qt.NoFocus)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(38)
    h = t.horizontalHeader()
    h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    h.setHighlightSections(False)
    h.setStretchLastSection(True)
    h.setMinimumSectionSize(60)
    t.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    t.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    return t


def spalten_anpassen(t: QTableWidget, extra: int = 6, maximal: int = 360):
    """Spaltenbreite nach Inhalt UND Überschrift, damit nichts abgeschnitten wird."""
    t.resizeColumnsToContents()
    fm = QFontMetrics(t.horizontalHeader().font())
    fett = QFont(t.horizontalHeader().font())
    fett.setWeight(QFont.DemiBold)
    fm = QFontMetrics(fett)
    for c in range(t.columnCount()):
        it = t.horizontalHeaderItem(c)
        kopf = fm.horizontalAdvance(it.text()) + 30 if it else 0
        t.setColumnWidth(c, min(max(t.columnWidth(c) + extra, kopf), maximal))


def tabelle_fuellen(t: QTableWidget, kopf: list[str], zeilen: list[list], fett_letzte: bool = False,
                    rechts: set[int] | None = None):
    t.setSortingEnabled(False)
    t.clear()
    t.setColumnCount(len(kopf))
    t.setHorizontalHeaderLabels(kopf)
    t.setRowCount(len(zeilen))
    for r, z in enumerate(zeilen):
        for c, v in enumerate(z):
            it = SortItem(v, v if isinstance(v, (int, float)) else str(v).lower())
            if isinstance(v, (int, float)) or (rechts and c in rechts):
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if fett_letzte and r == len(zeilen) - 1:
                fnt = it.font()
                fnt.setBold(True)
                it.setFont(fnt)
            t.setItem(r, c, it)
    if not fett_letzte:
        t.setSortingEnabled(True)
    for c in range(len(kopf)):
        if rechts and c in rechts:
            hi = t.horizontalHeaderItem(c)
            hi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)


def hoehe_an_inhalt(t: QTableWidget, min_zeilen: int = 3):
    """Tabelle so hoch wie ihr Inhalt (für Seiten mit eigener Bildlaufleiste)."""
    n = max(t.rowCount(), min_zeilen)
    h = t.horizontalHeader().sizeHint().height() + n * t.verticalHeader().defaultSectionSize() + 6
    if t.horizontalScrollBar().isVisible():
        h += t.horizontalScrollBar().height()
    t.setFixedHeight(h)
    t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)


# ------------------------------------------------------------------ Kacheln
class Kachel(QFrame):
    def __init__(self, titel: str, akzent: str = GRUEN, gross: bool = False):
        super().__init__()
        self.setObjectName("kachel")
        self.setStyleSheet(f"QFrame#kachel {{ border-left: 4px solid {akzent}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 14, 12)
        lay.setSpacing(2)
        self.titel = QLabel(titel)
        self.titel.setObjectName("kachelTitel")
        self.titel.setWordWrap(True)
        self.wert = QLabel("–")
        self.wert.setObjectName("kachelWertGross" if gross else "kachelWert")
        self.wert.setStyleSheet(f"color: {akzent};")
        self.unter = QLabel("")
        self.unter.setObjectName("kachelUnter")
        self.unter.setWordWrap(True)
        lay.addWidget(self.titel)
        lay.addWidget(self.wert)
        lay.addWidget(self.unter)
        lay.addStretch()
        self.setMinimumWidth(150)

    def setze(self, wert: str, unter: str = ""):
        self.wert.setText(wert)
        self.unter.setText(unter)
        self.unter.setVisible(bool(unter))


# ------------------------------------------------------------------ Avatar
class Avatar(QWidget):
    def __init__(self, groesse: int = 54):
        super().__init__()
        self.text = ""
        self.farbe = ("#dff1e4", GRUEN)
        self.setFixedSize(groesse, groesse)

    def setze(self, vorname: str, nachname: str, farbe: tuple[str, str] | None = None):
        self.text = ((vorname[:1] or "") + (nachname[:1] or "")).upper()
        if farbe:
            self.farbe = farbe
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.farbe[0]))
        p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        f = QFont(self.font())
        f.setPixelSize(int(self.height() * 0.36))
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(self.farbe[1]))
        p.drawText(self.rect(), Qt.AlignCenter, self.text)


# ------------------------------------------------------------------ Navigation
class NavKnopf(QPushButton):
    def __init__(self, text: str):
        super().__init__()
        self.setObjectName("nav")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 12, 0)
        self.name = QLabel(text)
        self.name.setObjectName("navText")
        self.zahl = QLabel("")
        self.zahl.setObjectName("navZahl")
        for l in (self.name, self.zahl):
            l.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self.name)
        lay.addStretch()
        lay.addWidget(self.zahl)

    def setze_zahl(self, n):
        self.zahl.setText(str(n) if n not in (None, "") else "")
        self.zahl.setVisible(n not in (None, ""))


class Chip(QPushButton):
    def __init__(self, text: str, schluessel: str):
        super().__init__(text)
        self.basis = text
        self.schluessel = schluessel
        self.setObjectName("chip")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)

    def setze_zahl(self, n: int):
        self.setText(f"{self.basis}  {n}")


# ------------------------------------------------------------------ Leerer Zustand
class LeerHinweis(QWidget):
    def __init__(self, titel: str, text: str, knoepfe: list[QPushButton] | None = None):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addStretch()
        t = QLabel(titel)
        t.setObjectName("leerTitel")
        t.setAlignment(Qt.AlignCenter)
        x = QLabel(text)
        x.setObjectName("leerText")
        x.setAlignment(Qt.AlignCenter)
        x.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(x)
        if knoepfe:
            h = QHBoxLayout()
            h.addStretch()
            for b in knoepfe:
                h.addWidget(b)
            h.addStretch()
            lay.addSpacing(8)
            lay.addLayout(h)
        lay.addStretch()


# ------------------------------------------------------------------ Diagramm
def _schoenes_maximum(m: float) -> tuple[float, float]:
    if m <= 4:
        return 4, 1
    roh = m / 4
    basis = 10 ** math.floor(math.log10(roh))
    for f in (1, 2, 5, 10):
        if basis * f >= roh:
            schritt = basis * f
            return schritt * 4, schritt
    return m, m / 4


class BalkenDiagramm(QWidget):
    """Einfaches (gruppiertes) Balkendiagramm ohne Zusatzbibliotheken."""

    def __init__(self, serien: list[tuple[str, str]]):
        super().__init__()
        self.serien = serien
        self.daten: list[tuple[str, list[float]]] = []
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def setze(self, daten: list[tuple[str, list[float]]]):
        self.daten = daten
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fm = QFontMetrics(self.font())
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        if not self.daten or all(sum(v) == 0 for _, v in self.daten):
            p.setPen(QColor(GRAU))
            p.drawText(r, Qt.AlignCenter, "Noch keine Daten")
            return
        legende_h = 0
        if len(self.serien) > 1:
            legende_h = fm.height() + 10
            x = r.right()
            for name, farbe in reversed(self.serien):
                w = fm.horizontalAdvance(name)
                x -= w
                p.setPen(QColor(GRAU))
                p.drawText(QRectF(x, r.top(), w, fm.height()), Qt.AlignVCenter, name)
                x -= 16
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(farbe))
                p.drawRoundedRect(QRectF(x, r.top() + fm.height() / 2 - 5, 10, 10), 2, 2)
                x -= 18
        maxv = max(max(v) for _, v in self.daten)
        oben, schritt = _schoenes_maximum(maxv)
        links = fm.horizontalAdvance(f"{int(oben)}") + 12
        unten = fm.height() + 10
        plot = QRectF(r.left() + links, r.top() + legende_h + fm.height() / 2 + 6,
                      r.width() - links, r.height() - legende_h - unten - fm.height() / 2 - 6)
        # Gitterlinien
        k = 0
        while k * schritt <= oben + 1e-9:
            y = plot.bottom() - (k * schritt / oben) * plot.height()
            p.setPen(QPen(QColor("#e6ebe7"), 1))
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            p.setPen(QColor(GRAU))
            wert = f"{k * schritt:g}"
            p.drawText(QRectF(r.left(), y - fm.height() / 2, links - 8, fm.height()), Qt.AlignRight | Qt.AlignVCenter, wert)
            k += 1
        n = len(self.daten)
        slot = plot.width() / n
        anz = len(self.serien)
        gruppe = min(slot * 0.72, 30 * anz + 4 * (anz - 1))
        balken = (gruppe - 4 * (anz - 1)) / anz
        klein = QFont(self.font())
        klein.setPointSizeF(self.font().pointSizeF() * 0.85)
        fmk = QFontMetrics(klein)
        for i, (label, werte) in enumerate(self.daten):
            x0 = plot.left() + i * slot + (slot - gruppe) / 2
            for j, v in enumerate(werte):
                h = (v / oben) * plot.height() if oben else 0
                rect = QRectF(x0 + j * (balken + 4), plot.bottom() - h, balken, h)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(self.serien[j][1]))
                if h > 0:
                    p.drawRoundedRect(rect, min(3, balken / 2), min(3, balken / 2))
                    p.fillRect(QRectF(rect.left(), rect.bottom() - min(3, h), rect.width(), min(3, h)),
                               QColor(self.serien[j][1]))
                if v and fmk.horizontalAdvance(f"{v:g}") <= balken + 10:
                    p.setFont(klein)
                    p.setPen(QColor(TEXT))
                    p.drawText(QRectF(rect.left() - 10, rect.top() - fmk.height() - 2, balken + 20, fmk.height()),
                               Qt.AlignCenter, f"{v:g}")
                    p.setFont(self.font())
            p.setPen(QColor(GRAU))
            text = fm.elidedText(str(label), Qt.ElideRight, int(slot - 4))
            p.drawText(QRectF(plot.left() + i * slot, plot.bottom() + 6, slot, fm.height()), Qt.AlignCenter, text)
        p.setPen(QPen(QColor("#c9d2cb"), 1))
        p.drawLine(int(plot.left()), int(plot.bottom()), int(plot.right()), int(plot.bottom()))


# ------------------------------------------------------------------ Stil
STIL = """
* { font-family: "Segoe UI", "Noto Sans", Arial; font-size: 10pt; color: #1d2a22; }
QMainWindow, QDialog { background: #f3f5f2; }
QWidget#seite, QWidget#seiteInhalt { background: #f3f5f2; }
QScrollArea { background: transparent; border: none; }
QToolTip { background: #1d2a22; color: #ffffff; border: none; padding: 5px 8px; }

/* Seitenleiste */
QFrame#sidebar { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #173f28, stop:1 #10301d); }
QFrame#sidebar QLabel { color: #d6e6db; background: transparent; }
QFrame#sidebar QLabel#logo { color: #ffffff; font-size: 21pt; font-weight: 700; }
QFrame#sidebar QLabel#logoUnter { color: #9fc2aa; font-size: 9pt; }
QFrame#sidebar QLabel#sidebarZahl { color: #ffffff; font-size: 24pt; font-weight: 700; }
QFrame#sidebar QLabel#sidebarKlein { color: #9fc2aa; font-size: 9pt; }
QFrame#trenner { background: #2b5a3d; max-height: 1px; min-height: 1px; border: none; }
QPushButton#nav { background: transparent; border: none; border-radius: 8px; text-align: left; margin: 0 10px; }
QPushButton#nav:hover { background: rgba(255,255,255,0.07); }
QPushButton#nav:checked { background: rgba(255,255,255,0.13); }
QPushButton#nav QLabel#navText { color: #d6e6db; font-size: 10.5pt; }
QPushButton#nav:checked QLabel#navText { color: #ffffff; font-weight: 600; }
QFrame#sidebar QLabel#navZahl { color: #cfe5d6; background: rgba(255,255,255,0.10); border-radius: 9px; padding: 1px 8px; font-size: 9pt; }
QPushButton#sidebarKnopf { background: transparent; color: #d6e6db; border: 1px solid #2f6243; border-radius: 7px;
                           padding: 8px 14px; text-align: left; }
QPushButton#sidebarKnopf:hover { background: rgba(255,255,255,0.08); }
QPushButton#sidebarPrimaer { background: #8fd19e; color: #10301d; border: none; border-radius: 7px; padding: 9px 12px;
                             font-weight: 600; }
QPushButton#sidebarPrimaer:hover { background: #a6dfb3; }
QPushButton#sidebarKnopf::menu-indicator { subcontrol-position: right center; right: 10px; }

/* Seitenkopf */
QLabel#seitenTitel { font-size: 19pt; font-weight: 600; color: #14361f; }
QLabel#seitenUntertitel { color: #6b766f; }
QLabel#abschnitt { font-size: 11pt; font-weight: 600; color: #1d2a22; }
QLabel#hinweis, QLabel#muted { color: #6b766f; }

/* Karten */
QFrame#karte { background: #ffffff; border: 1px solid #e1e7e2; border-radius: 10px; }
QFrame#karte QLabel { background: transparent; }
QFrame#infoBanner { background: #eaf4ed; border: 1px solid #cfe4d5; border-radius: 10px; }
QFrame#infoBanner QLabel { color: #24432f; background: transparent; }
QFrame#auswahlleiste { background: #14361f; border-radius: 9px; }
QFrame#auswahlleiste QLabel { color: #ffffff; font-weight: 600; background: transparent; }
QFrame#auswahlleiste QPushButton { background: rgba(255,255,255,0.12); color: #ffffff; border: none;
                                   border-radius: 6px; padding: 6px 12px; }
QFrame#auswahlleiste QPushButton:hover { background: rgba(255,255,255,0.22); }


/* Kacheln */
QFrame#kachel { background: #ffffff; border: 1px solid #e1e7e2; border-radius: 10px; }
QFrame#kachel QLabel { background: transparent; }
QLabel#kachelTitel { color: #6b766f; font-size: 9pt; }
QLabel#kachelWert { font-size: 19pt; font-weight: 600; }
QLabel#kachelWertGross { font-size: 26pt; font-weight: 700; }
QLabel#kachelUnter { color: #6b766f; font-size: 8.5pt; }

/* Leer-Zustand */
QLabel#leerTitel { font-size: 14pt; font-weight: 600; color: #1d2a22; }
QLabel#leerText { color: #6b766f; }

/* Knöpfe */
QPushButton { padding: 7px 14px; border-radius: 7px; }
QPushButton#primaer, QPushButton:default { background: #1f5130; color: #ffffff; border: 1px solid #1f5130; font-weight: 600; }
QPushButton#primaer:hover, QPushButton:default:hover { background: #2a6a40; }
QPushButton#primaer:disabled { background: #a9bdb0; border-color: #a9bdb0; }
QPushButton, QPushButton#sekundaer { background: #ffffff; border: 1px solid #cdd6cf; }
QPushButton:hover, QPushButton#sekundaer:hover { background: #f0f6f1; border-color: #b7c4ba; }
QPushButton:disabled, QPushButton#sekundaer:disabled, QPushButton#gefahr:disabled { color: #a3aca6; background: #f6f7f6; border-color: #e1e7e2; }
QPushButton#gefahr { background: #ffffff; color: #b42318; border: 1px solid #f0c4c0; }
QPushButton#gefahr:hover { background: #fdeceb; }
QPushButton#link { background: transparent; border: none; color: #2f7a4a; padding: 4px 6px; }
QPushButton#link:hover { color: #1f5130; text-decoration: underline; }
QPushButton#chip { background: #ffffff; border: 1px solid #d5ddd7; border-radius: 15px; padding: 5px 14px; color: #3c4a41; }
QPushButton#chip:hover { background: #f0f6f1; }
QPushButton#chip:checked { background: #1f5130; border-color: #1f5130; color: #ffffff; font-weight: 600; }

/* Eingabefelder */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QPlainTextEdit { padding: 6px 8px; border: 1px solid #cdd6cf;
        border-radius: 7px; background: #ffffff; selection-background-color: #2f7a4a; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QPlainTextEdit:focus { border: 1px solid #2f7a4a; }
QLineEdit:disabled, QDateEdit:disabled, QComboBox:disabled { color: #a3aca6; background: #f6f7f6; }
QLineEdit#suche { padding: 8px 12px; font-size: 10.5pt; }
QComboBox, QDateEdit { padding-right: 26px; }
QComboBox::drop-down, QDateEdit::drop-down { subcontrol-origin: padding; subcontrol-position: center right;
        border: none; width: 26px; }
QComboBox::down-arrow, QDateEdit::down-arrow { image: url(%ICONS%/runter.png); width: 11px; height: 11px; }
QComboBox::down-arrow:disabled, QDateEdit::down-arrow:disabled { image: url(%ICONS%/runter_grau.png); }
QSpinBox { padding-right: 22px; }
QSpinBox::up-button, QSpinBox::down-button { subcontrol-origin: border; width: 20px; border: none; background: transparent; }
QSpinBox::up-button { subcontrol-position: top right; margin-top: 3px; }
QSpinBox::down-button { subcontrol-position: bottom right; margin-bottom: 3px; }
QSpinBox::up-arrow { image: url(%ICONS%/hoch.png); width: 9px; height: 9px; }
QSpinBox::down-arrow { image: url(%ICONS%/runter.png); width: 9px; height: 9px; }
QComboBox QAbstractItemView { border: 1px solid #cdd6cf; selection-background-color: #dff1e4; selection-color: #14361f; outline: 0; }
QCheckBox, QRadioButton { spacing: 8px; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; border: 1.5px solid #9aa9a0; background: #ffffff; }
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 9px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: #2f7a4a; }
QCheckBox::indicator:checked { background: #1f5130; border-color: #1f5130; image: url(%ICONS%/check.png); }
QRadioButton::indicator:checked { border: 5px solid #1f5130; width: 9px; height: 9px; }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { background: #eef1ee; border-color: #cdd6cf; }

/* Tabellen */
QTableWidget { background: #ffffff; alternate-background-color: #f8faf8; border: none; outline: 0; }
QTableWidget::item { padding: 0 8px; border-bottom: 1px solid #eef1ee; }
QTableWidget::item:hover { background: #f0f6f1; }
QTableWidget::item:selected { background: #d6ecdc; color: #10301d; }
QHeaderView { background: #ffffff; border: none; }
QHeaderView::section { background: #ffffff; color: #5b665f; font-weight: 600; border: none;
                       border-bottom: 2px solid #e1e7e2; padding: 9px 10px; }
QHeaderView::section:hover { color: #1f5130; }
QTableCornerButton::section { background: #ffffff; border: none; }

/* Detailansicht */
QLabel#detailName { font-size: 16pt; font-weight: 600; color: #14361f; }
QTextBrowser#detailText { border: none; background: transparent; }

/* Reiter (in Dialogen) – Auswahl ohne Fettschrift, damit nichts abgeschnitten wird */
QTabWidget::pane { border: 1px solid #e1e7e2; background: #ffffff; border-radius: 8px; top: -1px; }
QTabBar::tab { padding: 8px 18px; background: transparent; border: none; border-bottom: 2px solid transparent;
               color: #5b665f; margin-right: 4px; }
QTabBar::tab:selected { color: #1f5130; border-bottom: 2px solid #1f5130; }
QTabBar::tab:hover { color: #1f5130; }

QGroupBox { border: 1px solid #e1e7e2; border-radius: 8px; margin-top: 12px; padding-top: 10px; background: #ffffff; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; font-weight: 600; }
QSplitter::handle { background: transparent; }
QStatusBar { background: #ffffff; color: #6b766f; border-top: 1px solid #e1e7e2; }
QStatusBar QLabel { color: #6b766f; }
QMenu { background: #ffffff; border: 1px solid #d5ddd7; padding: 4px; }
QMenu::item { padding: 7px 22px; border-radius: 5px; }
QMenu::item:selected { background: #dff1e4; color: #14361f; }
QMenu::separator { height: 1px; background: #e6ebe7; margin: 4px 8px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #c9d2cb; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #aab7ad; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #c9d2cb; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""

DETAIL_CSS = """
h4 { color: #6b766f; font-size: 9pt; font-weight: 600; margin-top: 14px; margin-bottom: 4px; }
td.k { color: #6b766f; padding-right: 14px; white-space: nowrap; }
td { padding: 3px 0; vertical-align: top; }
.grau { color: #7a857e; }
a { color: #2f7a4a; text-decoration: none; }
"""


def _icons_erzeugen() -> str:
    """Erzeugt kleine Symbole (Häkchen, Pfeile) als PNG für das Stylesheet."""
    import tempfile
    from pathlib import Path
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QPainterPath, QPixmap
    ordner = Path(tempfile.gettempdir()) / "care_icons"
    ordner.mkdir(exist_ok=True)

    def malen(name, farbe, punkte, breite=2.6):
        pm = QPixmap(48, 48)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(farbe), breite * 3)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        pfad = QPainterPath(QPointF(*punkte[0]))
        for pt in punkte[1:]:
            pfad.lineTo(QPointF(*pt))
        p.drawPath(pfad)
        p.end()
        pm.save(str(ordner / name))

    malen("check.png", "#ffffff", [(11, 25), (20, 34), (37, 15)])
    malen("runter.png", "#5b665f", [(10, 17), (24, 31), (38, 17)])
    malen("runter_grau.png", "#b5beb8", [(10, 17), (24, 31), (38, 17)])
    malen("hoch.png", "#5b665f", [(10, 31), (24, 17), (38, 31)])
    return ordner.as_posix()


def stil_erzeugen() -> str:
    """Komplettes Stylesheet inkl. Symbolen (erst nach QApplication aufrufen)."""
    try:
        return STIL.replace("%ICONS%", _icons_erzeugen())
    except Exception:  # noqa: BLE001 – ohne Symbole weiterarbeiten
        return STIL.replace("%ICONS%", ".")
