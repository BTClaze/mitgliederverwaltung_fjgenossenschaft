"""Hauptfenster der Mitgliederverwaltung (Seitenleiste + vier Seiten)."""
from __future__ import annotations

import html
from datetime import date, datetime
from pathlib import Path

from PyQt5.QtCore import QDate, Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QApplication, QButtonGroup, QHeaderView, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QScrollArea,
    QSplitter, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from . import excel_io, iban_utils
from .database import (
    ALLE_STATUS, STATUS_AUSGETRETEN, STATUS_AUSTRITT_ANGEMELDET, STATUS_KEIN, STATUS_MITGLIED,
    Datenbank, Person, heute_iso, iso_zu_de,
)
from .dialogs import (
    AustrittDialog, BeitrittDialog, EinstellungenDialog, ImportDialog, PersonDialog,
    datum_feld, qdate_zu_iso,
)
from .ui_elemente import (
    DETAIL_CSS, GELB, GRAU, GRUEN, GRUEN_HELL, ROT, STATUS_FARBEN, STIL, Avatar, BalkenDiagramm,
    Chip, Kachel, LeerHinweis, NavKnopf, SortItem, StatusDelegate, abschnitt_titel, hoehe_an_inhalt,
    karte, knopf, neue_tabelle, pille, seiten_kopf, spalten_anpassen, stil_erzeugen, tabelle_fuellen,
)

__all__ = ["Hauptfenster", "STIL", "stil_erzeugen"]

SEITE_PERSONEN, SEITE_AUSGETRETENE, SEITE_REVISION, SEITE_INFO = range(4)
STATUS_CHIPS = [("alle", "Alle"), (STATUS_MITGLIED, "Mitglieder"), (STATUS_AUSTRITT_ANGEMELDET, "Austritt angemeldet"),
                (STATUS_AUSGETRETEN, "Ausgetreten"), (STATUS_KEIN, "Nicht-Mitglieder")]


def euro(betrag: float) -> str:
    return f"{betrag:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class Hauptfenster(QMainWindow):
    def __init__(self, db: Datenbank):
        super().__init__()
        self.db = db
        self.iban_voll = False
        self.personen: list[Person] = []
        self.status_filter = "alle"
        self.resize(1440, 880)
        self.setMinimumSize(1100, 680)

        self._aktionen()
        wurzel = QWidget()
        wurzel.setObjectName("seite")
        lay = QHBoxLayout(wurzel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._seitenleiste())
        self.stack = QStackedWidget()
        self.stack.addWidget(self._seite_personen())
        self.stack.addWidget(self._seite_ausgetretene())
        self.stack.addWidget(self._seite_revision())
        self.stack.addWidget(self._seite_info())
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(wurzel)
        self.statusBar().showMessage(f"Datenbank: {db.pfad}")
        self.nav[0].setChecked(True)
        self.aktualisieren()

    # ============================================================ Aktionen / Tastenkürzel
    def _aktionen(self):
        def akt(text, slot, kurz=None):
            a = QAction(text, self)
            a.triggered.connect(slot)
            if kurz:
                a.setShortcut(QKeySequence(kurz))
            self.addAction(a)
            return a

        self.a_import = akt("Excel importieren …", self.excel_importieren, "Ctrl+I")
        self.a_neu = akt("Neue Person", self.person_neu, "Ctrl+N")
        self.a_bearbeiten = akt("Bearbeiten", self.person_bearbeiten, "Ctrl+E")
        self.a_beitritt = akt("Beitritt erfassen", self.beitritt, "Ctrl+B")
        self.a_austritt = akt("Austritt erfassen", self.austritt, "Ctrl+R")
        self.a_loeschen = akt("Löschen", self.person_loeschen, QKeySequence.Delete)
        self.a_export = akt("Ansicht als Excel exportieren …", self.ansicht_exportieren, "Ctrl+S")
        self.a_suche = akt("Suchen", lambda: (self._seite(SEITE_PERSONEN), self.suche.setFocus(), self.suche.selectAll()), "Ctrl+F")
        self.a_iban = QAction("IBANs vollständig anzeigen", self, checkable=True)
        self.a_iban.toggled.connect(self._iban_umschalten)
        self.a_vorlage = QAction("Importvorlage speichern …", self, triggered=self.vorlage_speichern)
        self.a_sichern = QAction("Datenbank sichern …", self, triggered=self.sichern)
        self.a_einst = QAction("Einstellungen …", self, triggered=self.einstellungen)
        self.a_ueber = QAction("Über C.A.R.E", self, triggered=self.ueber)
        self.a_beenden = akt("Beenden", self.close, "Ctrl+Q")

    # ============================================================ Seitenleiste
    def _seitenleiste(self) -> QFrame:
        sb = QFrame()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(236)
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(0, 22, 0, 18)
        lay.setSpacing(4)

        kopf = QVBoxLayout()
        kopf.setContentsMargins(26, 0, 20, 0)
        kopf.setSpacing(0)
        logo = QLabel("C.A.R.E")
        logo.setObjectName("logo")
        self.logo_unter = QLabel()
        self.logo_unter.setObjectName("logoUnter")
        self.logo_unter.setWordWrap(True)
        kopf.addWidget(logo)
        kopf.addWidget(self.logo_unter)
        lay.addLayout(kopf)
        lay.addSpacing(22)

        self.nav: list[NavKnopf] = []
        gruppe = QButtonGroup(self)
        gruppe.setExclusive(True)
        for i, text in enumerate(["Personen", "Ausgetretene", "Revision & Statistik", "Mitgliederinfo"]):
            b = NavKnopf(text)
            b.clicked.connect(lambda _, i=i: self._seite(i))
            gruppe.addButton(b)
            self.nav.append(b)
            lay.addWidget(b)
        lay.addStretch()

        stat = QVBoxLayout()
        stat.setContentsMargins(26, 0, 20, 0)
        stat.setSpacing(0)
        klein = QLabel("Mitglieder aktuell")
        klein.setObjectName("sidebarKlein")
        self.sb_zahl = QLabel("0")
        self.sb_zahl.setObjectName("sidebarZahl")
        self.sb_unter = QLabel("")
        self.sb_unter.setObjectName("sidebarKlein")
        self.sb_unter.setWordWrap(True)
        stat.addWidget(klein)
        stat.addWidget(self.sb_zahl)
        stat.addWidget(self.sb_unter)
        lay.addLayout(stat)
        lay.addSpacing(14)
        tr = QFrame()
        tr.setObjectName("trenner")
        lay.addWidget(tr)
        lay.addSpacing(10)

        unten = QVBoxLayout()
        unten.setContentsMargins(18, 0, 18, 0)
        unten.setSpacing(8)
        imp = knopf("Excel importieren", "sidebarPrimaer", self.excel_importieren, "Klassenliste aus Excel/CSV übernehmen (Strg+I)")
        mehr = knopf("•••   Mehr", "sidebarKnopf")
        m = QMenu(mehr)
        for a in (self.a_einst, None, self.a_vorlage, self.a_sichern, None, self.a_iban, None, self.a_ueber, self.a_beenden):
            m.addSeparator() if a is None else m.addAction(a)
        self._mehr_menue = m
        mehr.clicked.connect(lambda: m.exec_(mehr.mapToGlobal(mehr.rect().topLeft()) - __import__("PyQt5.QtCore", fromlist=["QPoint"]).QPoint(0, m.sizeHint().height() + 4)))
        unten.addWidget(imp)
        unten.addWidget(mehr)
        lay.addLayout(unten)
        return sb

    def _seite(self, i: int):
        self.stack.setCurrentIndex(i)
        self.nav[i].setChecked(True)
        self.aktualisieren()

    def _seiten_rahmen(self) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        w.setObjectName("seite")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(16)
        return w, lay

    # ============================================================ Seite: Personen
    def _seite_personen(self) -> QWidget:
        w, lay = self._seiten_rahmen()
        kopf, self.p_unter = seiten_kopf(
            "Personen & Mitglieder", "",
            [knopf("Exportieren", "sekundaer", self.ansicht_exportieren, "Gefilterte Liste als Excel speichern (Strg+S)"),
             knopf("Excel importieren", "sekundaer", self.excel_importieren),
             knopf("+  Neue Person", "primaer", self.person_neu)])
        lay.addWidget(kopf)

        # Filter
        fk, fl = karte(14, 12)
        z1 = QHBoxLayout()
        z1.setSpacing(10)
        self.suche = QLineEdit()
        self.suche.setObjectName("suche")
        self.suche.setPlaceholderText("Suchen nach Name, Mitglieds-Nr., E-Mail, IBAN …   (Strg+F)")
        self.suche.setClearButtonEnabled(True)
        self.f_klasse = QComboBox()
        self.f_klasse.setMinimumWidth(150)
        self.f_iban = QComboBox()
        self.f_iban.addItems(["IBAN: alle", "IBAN fehlt", "IBAN ungültig", "IBAN gültig"])
        self.f_iban.setMinimumWidth(140)
        z1.addWidget(self.suche, 1)
        z1.addWidget(self.f_klasse)
        z1.addWidget(self.f_iban)
        z1.addWidget(knopf("Zurücksetzen", "link", self._filter_zuruecksetzen))
        fl.addLayout(z1)
        z2 = QHBoxLayout()
        z2.setSpacing(8)
        self.chips: list[Chip] = []
        self.chip_gruppe = QButtonGroup(self)
        for schl, text in STATUS_CHIPS:
            c = Chip(text, schl)
            c.clicked.connect(lambda _, s=schl: self._status_setzen(s))
            self.chip_gruppe.addButton(c)
            self.chips.append(c)
            z2.addWidget(c)
        self.chips[0].setChecked(True)
        z2.addStretch()
        fl.addLayout(z2)
        lay.addWidget(fk)
        self.suche.textChanged.connect(lambda _: self._tabelle_fuellen())
        for cb in (self.f_klasse, self.f_iban):
            cb.currentIndexChanged.connect(lambda _: self._tabelle_fuellen())

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(14)
        split.setChildrenCollapsible(False)

        # Tabelle
        tk, tl = karte(0, 0)
        self.p_stapel = QStackedWidget()
        self.tabelle = neue_tabelle(mehrfachauswahl=True)
        self.spalten = ["Nr.", "Nachname", "Vorname", "Klasse", "Status", "Beitritt", "Austritt", "Anteile", "IBAN", "E-Mail"]
        self.tabelle.setColumnCount(len(self.spalten))
        self.tabelle.setHorizontalHeaderLabels(self.spalten)
        self.tabelle.setItemDelegateForColumn(4, StatusDelegate(self.tabelle))
        self.tabelle.itemSelectionChanged.connect(self._auswahl_geaendert)
        self.tabelle.doubleClicked.connect(lambda _: self.person_bearbeiten())
        self.tabelle.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabelle.customContextMenuRequested.connect(self._kontextmenue)
        self.p_stapel.addWidget(self.tabelle)
        self.p_stapel.addWidget(LeerHinweis(
            "Noch keine Personen erfasst",
            "Importiere eine Klassenliste aus Excel oder lege eine Person von Hand an.",
            [knopf("Klassenliste importieren", "primaer", self.excel_importieren),
             knopf("Person anlegen", "sekundaer", self.person_neu)]))
        self.p_stapel.addWidget(LeerHinweis("Keine Treffer", "Für diese Suche bzw. diese Filter gibt es keine Personen.",
                                            [knopf("Filter zurücksetzen", "sekundaer", self._filter_zuruecksetzen)]))
        tl.addWidget(self.p_stapel, 1)

        # Fußleiste: normal = Anzahl, bei Auswahl = dunkle Aktionsleiste
        fuss = QWidget()
        fuss_l = QVBoxLayout(fuss)
        fuss_l.setContentsMargins(10, 8, 10, 10)
        self.normal_leiste = QWidget()
        nl = QHBoxLayout(self.normal_leiste)
        nl.setContentsMargins(6, 0, 0, 0)
        self.anzahl_info = QLabel()
        self.anzahl_info.setObjectName("muted")
        nl.addWidget(self.anzahl_info)
        nl.addStretch()
        nl.addWidget(QLabel("<span style='color:#6b766f'>Tipp: Strg/Umschalt + Klick wählt mehrere aus</span>"))
        nl.addWidget(knopf("Alle auswählen", "link", self.tabelle.selectAll))
        self.auswahl_leiste = QFrame()
        self.auswahl_leiste.setObjectName("auswahlleiste")
        al = QHBoxLayout(self.auswahl_leiste)
        al.setContentsMargins(14, 7, 8, 7)
        self.auswahl_text = QLabel()
        al.addWidget(self.auswahl_text)
        al.addStretch()
        self.l_beitritt = knopf("✓  Beitritt erfassen", "sekundaer", self.beitritt)
        self.l_austritt = knopf("Austritt erfassen", "sekundaer", self.austritt)
        self.l_bearbeiten = knopf("Bearbeiten", "sekundaer", self.person_bearbeiten)
        self.l_loeschen = knopf("Löschen", "sekundaer", self.person_loeschen)
        self.l_aufheben = knopf("✕", "sekundaer", self.tabelle.clearSelection, "Auswahl aufheben")
        for b in (self.l_beitritt, self.l_austritt, self.l_bearbeiten, self.l_loeschen, self.l_aufheben):
            al.addWidget(b)
        fuss_l.addWidget(self.normal_leiste)
        fuss_l.addWidget(self.auswahl_leiste)
        tl.addWidget(fuss)
        split.addWidget(tk)

        # Detail
        dk, dl = karte(20, 12)
        dk.setMinimumWidth(340)
        self.d_stapel = QStackedWidget()
        self.d_stapel.addWidget(LeerHinweis("Keine Person ausgewählt",
                                            "Klicke in der Liste auf eine Person, um alle Details zu sehen."))
        # Einzelperson
        einzel = QWidget()
        el = QVBoxLayout(einzel)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(10)
        k = QHBoxLayout()
        k.setSpacing(14)
        self.avatar = Avatar(56)
        k.addWidget(self.avatar, 0, Qt.AlignTop)
        kv = QVBoxLayout()
        kv.setSpacing(6)
        self.d_name = QLabel()
        self.d_name.setObjectName("detailName")
        self.d_name.setWordWrap(True)
        self.d_zeile = QHBoxLayout()
        self.d_zeile.setSpacing(8)
        kv.addWidget(self.d_name)
        kv.addLayout(self.d_zeile)
        k.addLayout(kv, 1)
        el.addLayout(k)
        self.d_text = QTextBrowser()
        self.d_text.setObjectName("detailText")
        self.d_text.setOpenLinks(False)
        self.d_text.document().setDefaultStyleSheet(DETAIL_CSS)
        self.d_text.anchorClicked.connect(self._detail_link)
        el.addWidget(self.d_text, 1)
        kn = QGridLayout()
        kn.setSpacing(8)
        self.d_bearbeiten = knopf("Bearbeiten", "sekundaer", self.person_bearbeiten)
        self.d_notiz = knopf("Notiz hinzufügen", "sekundaer", self.notiz)
        self.d_beitritt = knopf("✓  Beitritt erfassen", "primaer", self.beitritt)
        self.d_austritt = knopf("Austritt erfassen", "gefahr", self.austritt)
        kn.addWidget(self.d_bearbeiten, 0, 0)
        kn.addWidget(self.d_notiz, 0, 1)
        kn.addWidget(self.d_beitritt, 1, 0, 1, 2)
        kn.addWidget(self.d_austritt, 2, 0, 1, 2)
        el.addLayout(kn)
        self.d_stapel.addWidget(einzel)
        # Mehrfachauswahl
        mehr = QWidget()
        ml = QVBoxLayout(mehr)
        ml.setContentsMargins(0, 0, 0, 0)
        self.m_titel = QLabel()
        self.m_titel.setObjectName("detailName")
        self.m_text = QLabel()
        self.m_text.setWordWrap(True)
        self.m_text.setTextFormat(Qt.RichText)
        ml.addWidget(self.m_titel)
        ml.addSpacing(6)
        ml.addWidget(self.m_text)
        ml.addStretch()
        self.m_beitritt = knopf("✓  Beitritt für Auswahl", "primaer", self.beitritt)
        self.m_austritt = knopf("Austritt für Auswahl", "gefahr", self.austritt)
        ml.addWidget(self.m_beitritt)
        ml.addWidget(self.m_austritt)
        self.d_stapel.addWidget(mehr)
        dl.addWidget(self.d_stapel)
        split.addWidget(dk)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([900, 400])
        lay.addWidget(split, 1)
        return w

    def _status_setzen(self, schl: str):
        self.status_filter = schl
        for c in self.chips:
            c.setChecked(c.schluessel == schl)
        self._tabelle_fuellen()

    def _filter_zuruecksetzen(self):
        self.suche.clear()
        self.f_klasse.setCurrentIndex(0)
        self.f_iban.setCurrentIndex(0)
        self._status_setzen("alle")

    def _gefiltert(self, ohne_status: bool = False) -> list[Person]:
        q = self.suche.text().strip().lower()
        kl = self.f_klasse.currentText()
        ib = self.f_iban.currentIndex()
        out = []
        for p in self.personen:
            if not ohne_status and self.status_filter != "alle" and p.status != self.status_filter:
                continue
            if kl and kl != "Alle Klassen" and p.klasse != kl:
                continue
            if ib == 1 and p.iban:
                continue
            if ib == 2 and (not p.iban or p.iban_gueltig):
                continue
            if ib == 3 and not p.iban_gueltig:
                continue
            if q:
                heu = " ".join(str(x) for x in (p.vorname, p.nachname, p.klasse, p.email, p.iban,
                                                p.mitglieds_nr or "", p.notizen)).lower()
                if not all(teil in heu for teil in q.split()):
                    continue
            out.append(p)
        return out

    def _iban_text(self, p: Person) -> str:
        if not p.iban:
            return ""
        t = iban_utils.formatieren(p.iban) if self.iban_voll else iban_utils.maskieren(p.iban)
        return ("⚠ " + t) if not p.iban_gueltig else t

    def _tabelle_fuellen(self):
        # Zähler auf den Status-Schaltflächen (berücksichtigen Suche/Klasse/IBAN)
        basis = self._gefiltert(ohne_status=True)
        for c in self.chips:
            c.setze_zahl(len(basis) if c.schluessel == "alle" else sum(1 for p in basis if p.status == c.schluessel))
        ausgewaehlt = set(self._ausgewaehlte_ids())
        sichtbar = self._gefiltert()
        t = self.tabelle
        t.setSortingEnabled(False)
        t.blockSignals(True)
        t.clearContents()
        t.setRowCount(len(sichtbar))
        for r, p in enumerate(sichtbar):
            zellen = [
                SortItem(p.mitglieds_nr or "", p.mitglieds_nr or 10 ** 9),
                SortItem(p.nachname, p.nachname.lower()),
                SortItem(p.vorname, p.vorname.lower()),
                SortItem(p.klasse, p.klasse.lower()),
                SortItem(p.status, ALLE_STATUS.index(p.status)),
                SortItem(iso_zu_de(p.beitritt_datum), p.beitritt_datum or "9999"),
                SortItem(iso_zu_de(p.austritt_datum), p.austritt_datum or "9999"),
                SortItem(p.anteile if p.beitritt_datum else "", p.anteile if p.beitritt_datum else -1),
                SortItem(self._iban_text(p), p.iban),
                SortItem(p.email, p.email.lower()),
            ]
            zellen[0].setData(Qt.UserRole, p.id)
            zellen[0].setForeground(QColor(GRAU))
            zellen[7].setTextAlignment(Qt.AlignCenter)
            fnt = zellen[1].font()
            fnt.setWeight(600)
            zellen[1].setFont(fnt)
            if p.iban and not p.iban_gueltig:
                zellen[8].setForeground(QColor(ROT))
                zellen[8].setToolTip(iban_utils.pruefen(p.iban)[1])
            for c, it in enumerate(zellen):
                t.setItem(r, c, it)
            if p.id in ausgewaehlt:
                for it in zellen:
                    it.setSelected(True)
        t.setSortingEnabled(True)
        t.blockSignals(False)
        spalten_anpassen(t)
        self.p_stapel.setCurrentIndex(0 if sichtbar else (1 if not self.personen else 2))
        self._auswahl_geaendert()

    def _ausgewaehlte_ids(self) -> list[int]:
        if not hasattr(self, "tabelle"):
            return []
        ids = []
        for r in sorted({i.row() for i in self.tabelle.selectedItems()}):
            it = self.tabelle.item(r, 0)
            if it is not None:
                ids.append(it.data(Qt.UserRole))
        return ids

    def _ausgewaehlte(self) -> list[Person]:
        nach_id = {p.id: p for p in self.personen}
        return [nach_id[i] for i in self._ausgewaehlte_ids() if i in nach_id]

    def _auswahl_geaendert(self):
        ausw = self._ausgewaehlte()
        n = len(ausw)
        self.anzahl_info.setText(f"{self.tabelle.rowCount()} von {len(self.personen)} Personen angezeigt")
        kann_beitreten = any(p.status in (STATUS_KEIN, STATUS_AUSGETRETEN) for p in ausw)
        kann_austreten = any(p.status == STATUS_MITGLIED for p in ausw)
        for a, ok in ((self.a_bearbeiten, n == 1), (self.a_beitritt, kann_beitreten),
                      (self.a_austritt, kann_austreten), (self.a_loeschen, n >= 1)):
            a.setEnabled(ok)
        self.normal_leiste.setVisible(n == 0)
        self.auswahl_leiste.setVisible(n > 0)
        self.auswahl_text.setText(f"{n} ausgewählt")
        self.l_beitritt.setVisible(kann_beitreten)
        self.l_austritt.setVisible(kann_austreten)
        self.l_bearbeiten.setVisible(n == 1)
        if n == 1:
            self.d_stapel.setCurrentIndex(1)
            self._detail_zeigen(ausw[0].id)
        elif n > 1:
            self.d_stapel.setCurrentIndex(2)
            zaehl: dict[str, int] = {}
            for p in ausw:
                zaehl[p.status] = zaehl.get(p.status, 0) + 1
            self.m_titel.setText(f"{n} Personen ausgewählt")
            zeilen = "".join(
                f"<tr><td style='padding:4px 12px 4px 0'><span style='background:{STATUS_FARBEN[s][0]};"
                f"color:{STATUS_FARBEN[s][1]};font-weight:600'>&nbsp;{html.escape(s)}&nbsp;</span></td>"
                f"<td style='padding:4px 0'><b>{zaehl[s]}</b></td></tr>" for s in ALLE_STATUS if s in zaehl)
            klassen = sorted({p.klasse for p in ausw if p.klasse})
            self.m_text.setText(f"<table>{zeilen}</table><p style='color:{GRAU}'>Klassen: "
                                f"{html.escape(', '.join(klassen) or '–')}</p><p style='color:{GRAU}'>Beitritt oder "
                                "Austritt wird für alle passenden Personen gemeinsam eingetragen.</p>")
            self.m_beitritt.setEnabled(kann_beitreten)
            self.m_austritt.setEnabled(kann_austreten)
        else:
            self.d_stapel.setCurrentIndex(0)

    def _detail_zeigen(self, pid: int):
        p = self.db.person(pid)
        if p is None:
            return
        e = html.escape
        bg, fg = STATUS_FARBEN[p.status]
        self.avatar.setze(p.vorname, p.nachname, (bg, fg))
        self.d_name.setText(f"{p.vorname} {p.nachname}")
        while self.d_zeile.count():
            it = self.d_zeile.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.d_zeile.addWidget(pille(p.status, bg, fg))
        if p.klasse:
            self.d_zeile.addWidget(pille(p.klasse, "#eef1ee", "#3c4a41"))
        if p.mitglieds_nr:
            self.d_zeile.addWidget(pille(f"Nr. {p.mitglieds_nr}", "#eef1ee", "#3c4a41"))
        self.d_zeile.addStretch()

        def zeile(k, v):
            return f"<tr><td class='k'>{e(k)}</td><td>{v}</td></tr>" if v not in (None, "") else ""

        # Mitgliedschaft
        if p.beitritt_datum:
            mitgl = zeile("Beitritt", e(iso_zu_de(p.beitritt_datum)))
            mitgl += zeile("Geschäftsanteile", f"{p.anteile} &nbsp;<span class='grau'>({e(euro(p.anteile * self.db.betrag_pro_anteil()))})</span>")
            if p.austritt_datum:
                farbe = GELB if p.status == STATUS_AUSTRITT_ANGEMELDET else ROT
                mitgl += zeile("Austritt", f"<span style='color:{farbe}'>{e(iso_zu_de(p.austritt_datum))}</span>")
                mitgl += zeile("Grund", e(p.austritt_grund))
        else:
            mitgl = "<tr><td class='grau'>Noch keine Beitrittserklärung erfasst.</td></tr>"
        # Bank
        if p.iban:
            ok, msg = iban_utils.pruefen(p.iban)
            anz = iban_utils.formatieren(p.iban) if self.iban_voll else iban_utils.maskieren(p.iban)
            bank = zeile("IBAN", f"<span style='font-family:Consolas,monospace'>{e(anz)}</span>")
            bank += zeile("", f"<span style='color:{GRUEN_HELL if ok else ROT}'>{'✔' if ok else '✖'} {e(msg)}</span><br>"
                              f"<a href='iban:toggle'>{'verbergen' if self.iban_voll else 'anzeigen'}</a>"
                              f" &nbsp; <a href='iban:copy'>kopieren</a>")
            bank += zeile("BIC", e(p.bic))
            bank += zeile("Kontoinhaber", e(p.kontoinhaber))
        else:
            bank = f"<tr><td style='color:{ROT}'>Keine IBAN hinterlegt.</td></tr>"
        # Kontakt
        kontakt = zeile("Geburtsdatum", e(iso_zu_de(p.geburtsdatum)))
        if p.email:
            kontakt += (f"<tr><td class='k' colspan='2'>E-Mail</td></tr>"
                        f"<tr><td colspan='2'><a href='mailto:{e(p.email)}'>{e(p.email)}</a></td></tr>")
        kontakt += zeile("Telefon", e(p.telefon))
        kontakt += zeile("Adresse", "<br>".join(e(x) for x in (p.adresse, f"{p.plz} {p.ort}".strip()) if x))
        kontakt += zeile("Mitgliederinfo", "erwünscht" if p.info_erwuenscht else "<span class='grau'>nicht erwünscht</span>")
        farben = {"Beitritt": GRUEN_HELL, "Austritt": ROT, "Info": "#2563a8", "Notiz": GELB}
        verlauf = "".join(
            f"<tr><td class='k'>{e(iso_zu_de(ev['datum']))}</td><td><b style='color:{farben.get(ev['art'], '#3c4a41')}'>"
            f"{e(ev['art'])}</b>&nbsp; {e(ev['beschreibung'] or '')}</td></tr>" for ev in p.ereignisse)
        notizen = f"<h4>NOTIZEN</h4><p>{e(p.notizen).replace(chr(10), '<br>')}</p>" if p.notizen else ""
        self.d_text.setHtml(
            f"<h4>MITGLIEDSCHAFT</h4><table>{mitgl}</table>"
            f"<h4>BANKVERBINDUNG</h4><table>{bank}</table>"
            f"<h4>KONTAKT</h4><table>{kontakt or '<tr><td class=grau>keine Angaben</td></tr>'}</table>"
            f"{notizen}<h4>VERLAUF</h4><table>{verlauf}</table>")
        self.d_beitritt.setVisible(p.status in (STATUS_KEIN, STATUS_AUSGETRETEN))
        self.d_beitritt.setText("✓  Wiedereintritt erfassen" if p.status == STATUS_AUSGETRETEN else "✓  Beitritt erfassen")
        self.d_austritt.setVisible(p.status == STATUS_MITGLIED)

    def _detail_link(self, url: QUrl):
        s = url.toString()
        ausw = self._ausgewaehlte()
        if s == "iban:toggle":
            self.a_iban.toggle()
        elif s == "iban:copy" and ausw:
            QApplication.clipboard().setText(iban_utils.normalisieren(ausw[0].iban))
            self.statusBar().showMessage("IBAN in die Zwischenablage kopiert", 3000)
        elif s.startswith("mailto:"):
            QDesktopServices.openUrl(url)

    def _kontextmenue(self, pos):
        m = QMenu(self)
        for a in (self.a_bearbeiten, self.a_beitritt, self.a_austritt, None, self.a_loeschen):
            m.addSeparator() if a is None else m.addAction(a)
        m.exec_(self.tabelle.viewport().mapToGlobal(pos))

    def _iban_umschalten(self, an: bool):
        self.iban_voll = an
        self.aktualisieren()

    # ============================================================ Seite: Ausgetretene
    def _seite_ausgetretene(self) -> QWidget:
        w, lay = self._seiten_rahmen()
        kopf, _ = seiten_kopf("Ausgetretene Mitglieder",
                              "Fertige Liste aller Austritte – mit Auszahlungsbetrag der Geschäftsanteile und IBAN.",
                              [knopf("Liste als Excel speichern", "primaer", self._ausgetretene_exportieren)])
        lay.addWidget(kopf)
        fk, fl = karte(14, 10)
        f = QHBoxLayout()
        f.setSpacing(10)
        self.a_alle = QCheckBox("Alle Zeiträume")
        self.a_alle.setChecked(True)
        self.a_von = datum_feld(f"{date.today().year}-01-01")
        self.a_bis = datum_feld(f"{date.today().year}-12-31")
        self.a_klasse = QComboBox()
        self.a_klasse.setMinimumWidth(150)
        for x in (self.a_von, self.a_bis):
            x.setEnabled(False)
            x.dateChanged.connect(lambda _: self._ausgetretene_fuellen())
        self.a_alle.toggled.connect(lambda an: (self.a_von.setEnabled(not an), self.a_bis.setEnabled(not an),
                                                self._ausgetretene_fuellen()))
        self.a_klasse.currentIndexChanged.connect(lambda _: self._ausgetretene_fuellen())
        self.a_angemeldet = QCheckBox("auch angemeldete (künftige) Austritte")
        self.a_angemeldet.setChecked(True)
        self.a_angemeldet.toggled.connect(lambda _: self._ausgetretene_fuellen())
        f.addWidget(self.a_alle)
        f.addSpacing(6)
        f.addWidget(QLabel("Austritt von"))
        f.addWidget(self.a_von)
        f.addWidget(QLabel("bis"))
        f.addWidget(self.a_bis)
        f.addSpacing(16)
        f.addWidget(QLabel("Klasse"))
        f.addWidget(self.a_klasse)
        f.addSpacing(16)
        f.addWidget(self.a_angemeldet)
        f.addStretch()
        fl.addLayout(f)
        lay.addWidget(fk)

        kach = QHBoxLayout()
        kach.setSpacing(14)
        self.ak_anzahl = Kachel("Austritte", ROT)
        self.ak_anteile = Kachel("Geschäftsanteile", GRUEN)
        self.ak_betrag = Kachel("Auszahlung gesamt", GRUEN)
        self.ak_iban = Kachel("Ohne gültige IBAN", GELB)
        for k in (self.ak_anzahl, self.ak_anteile, self.ak_betrag, self.ak_iban):
            kach.addWidget(k)
        lay.addLayout(kach)

        tk, tl = karte(0, 0)
        self.a_stapel = QStackedWidget()
        self.a_tabelle = neue_tabelle()
        self.a_tabelle.doubleClicked.connect(self._ausgetretene_oeffnen)
        self.a_tabelle.setToolTip("Doppelklick öffnet die Person")
        self.a_stapel.addWidget(self.a_tabelle)
        self.a_stapel.addWidget(LeerHinweis("Keine Austritte", "Für diese Auswahl gibt es keine ausgetretenen Mitglieder."))
        tl.addWidget(self.a_stapel)
        lay.addWidget(tk, 1)
        return w

    def _ausgetretene(self) -> list[Person]:
        von, bis = qdate_zu_iso(self.a_von.date()), qdate_zu_iso(self.a_bis.date())
        kl = self.a_klasse.currentText()
        erlaubt = {STATUS_AUSGETRETEN} | ({STATUS_AUSTRITT_ANGEMELDET} if self.a_angemeldet.isChecked() else set())
        out = [p for p in self.personen if p.status in erlaubt
               and (self.a_alle.isChecked() or von <= p.austritt_datum <= bis)
               and (not kl or kl == "Alle Klassen" or p.klasse == kl)]
        return sorted(out, key=lambda p: (p.austritt_datum, p.nachname.lower()))

    def _ausgetretene_fuellen(self):
        liste = self._ausgetretene()
        betrag = self.db.betrag_pro_anteil()
        kopf = ["Nr.", "Nachname", "Vorname", "Klasse", "Beitritt", "Austritt", "Grund", "Anteile",
                "Auszahlung", "IBAN", "E-Mail"]
        t = self.a_tabelle
        t.setSortingEnabled(False)
        t.clear()
        t.setColumnCount(len(kopf))
        t.setHorizontalHeaderLabels(kopf)
        t.setRowCount(len(liste))
        for r, p in enumerate(liste):
            zellen = [SortItem(p.mitglieds_nr or "", p.mitglieds_nr or 0), SortItem(p.nachname),
                      SortItem(p.vorname), SortItem(p.klasse),
                      SortItem(iso_zu_de(p.beitritt_datum), p.beitritt_datum),
                      SortItem(iso_zu_de(p.austritt_datum), p.austritt_datum), SortItem(p.austritt_grund),
                      SortItem(p.anteile, p.anteile),
                      SortItem(euro(p.anteile * betrag), p.anteile * betrag),
                      SortItem(self._iban_text(p) or "fehlt", p.iban), SortItem(p.email)]
            zellen[0].setData(Qt.UserRole, p.id)
            zellen[0].setForeground(QColor(GRAU))
            fnt = zellen[1].font()
            fnt.setWeight(600)
            zellen[1].setFont(fnt)
            zellen[7].setTextAlignment(Qt.AlignCenter)
            zellen[8].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if p.status == STATUS_AUSTRITT_ANGEMELDET:
                zellen[5].setForeground(QColor(GELB))
                zellen[5].setText(zellen[5].text() + "  (angemeldet)")
            if not p.iban or not p.iban_gueltig:
                zellen[9].setForeground(QColor(ROT))
            for c, it in enumerate(zellen):
                t.setItem(r, c, it)
        t.setSortingEnabled(True)
        spalten_anpassen(t)
        self.a_stapel.setCurrentIndex(0 if liste else 1)
        anteile = sum(p.anteile for p in liste)
        ohne = sum(1 for p in liste if not p.iban_gueltig)
        angemeldet = sum(1 for p in liste if p.status == STATUS_AUSTRITT_ANGEMELDET)
        self.ak_anzahl.setze(str(len(liste)), f"davon {angemeldet} angemeldet" if angemeldet else "")
        self.ak_anteile.setze(str(anteile))
        self.ak_betrag.setze(euro(anteile * betrag), f"{euro(betrag)} pro Anteil")
        self.ak_iban.setze(str(ohne), "bitte IBAN nachfordern" if ohne else "alles vollständig")

    def _ausgetretene_oeffnen(self, idx):
        self._zu_person_springen(self.a_tabelle.item(idx.row(), 0).data(Qt.UserRole))

    def _ausgetretene_exportieren(self):
        liste = self._ausgetretene()
        if not liste:
            QMessageBox.information(self, "Keine Daten", "Die Liste ist leer.")
            return
        pfad = self._speichern_dialog(f"Ausgetretene_{date.today():%Y-%m-%d}.xlsx")
        if pfad:
            titel = f"{self.db.einstellung('name')} – Liste der ausgetretenen Mitglieder"
            if not self.a_alle.isChecked():
                titel += f" ({self.a_von.date().toString('dd.MM.yyyy')} – {self.a_bis.date().toString('dd.MM.yyyy')})"
            excel_io.ausgetretene_exportieren(pfad, liste, titel, self.db.betrag_pro_anteil())
            self._gespeichert(pfad)

    # ============================================================ Seite: Revision
    def _seite_revision(self) -> QWidget:
        aussen = QWidget()
        aussen.setObjectName("seite")
        al = QVBoxLayout(aussen)
        al.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        w, lay = self._seiten_rahmen()
        w.setObjectName("seiteInhalt")
        scroll.setWidget(w)
        al.addWidget(scroll)

        kopf, _ = seiten_kopf("Revision & Statistik",
                              "Mitgliederstand, Beitritte und Austritte für die Prüfung durch den Revisionsverband.",
                              [knopf("Revisionsbericht als Excel", "primaer", self._revision_exportieren)])
        lay.addWidget(kopf)

        fk, fl = karte(14, 10)
        f = QHBoxLayout()
        f.setSpacing(10)
        self.r_vorlage = QComboBox()
        jahr = date.today().year
        sj = jahr if date.today().month >= 9 else jahr - 1
        self.r_vorlage.addItems([f"Kalenderjahr {jahr}", f"Kalenderjahr {jahr - 1}",
                                 f"Schuljahr {sj}/{(sj + 1) % 100:02d}", "Benutzerdefiniert"])
        self.r_vorlage.setMinimumWidth(215)
        self.r_von = datum_feld(f"{jahr}-01-01")
        self.r_bis = datum_feld(f"{jahr}-12-31")
        self.r_stichtag = datum_feld(heute_iso())
        self.r_vorlage.currentIndexChanged.connect(self._revision_vorlage)
        for x in (self.r_von, self.r_bis, self.r_stichtag):
            x.dateChanged.connect(lambda _: self._revision_fuellen())
        f.addWidget(QLabel("Zeitraum"))
        f.addWidget(self.r_vorlage)
        f.addWidget(self.r_von)
        f.addWidget(QLabel("bis"))
        f.addWidget(self.r_bis)
        f.addSpacing(24)
        f.addWidget(QLabel("Stichtag für den Mitgliederstand"))
        f.addWidget(self.r_stichtag)
        f.addStretch()
        fl.addLayout(f)
        lay.addWidget(fk)

        g = QGridLayout()
        g.setSpacing(14)
        self.rk_stand = Kachel("Mitgliederstand am Stichtag", GRUEN, gross=True)
        self.rk_beginn = Kachel("Stand zu Beginn des Zeitraums", "#5b8a6b")
        self.rk_bei = Kachel("Beitritte im Zeitraum", GRUEN_HELL)
        self.rk_aus = Kachel("Austritte im Zeitraum", ROT)
        self.rk_anteile = Kachel("Geschäftsanteile", "#2563a8")
        self.rk_guthaben = Kachel("Geschäftsguthaben", "#2563a8")
        self.rk_iban = Kachel("IBAN fehlt / ungültig", GELB)
        g.addWidget(self.rk_stand, 0, 0, 2, 1)
        for i, k in enumerate((self.rk_beginn, self.rk_bei, self.rk_aus)):
            g.addWidget(k, 0, i + 1)
        for i, k in enumerate((self.rk_anteile, self.rk_guthaben, self.rk_iban)):
            g.addWidget(k, 1, i + 1)
        for c in range(4):
            g.setColumnStretch(c, 1)
        lay.addLayout(g)

        diag = QHBoxLayout()
        diag.setSpacing(14)
        k1, l1 = karte(18, 8)
        l1.addWidget(abschnitt_titel("Mitglieder je Klasse"))
        self.d_klasse = BalkenDiagramm([("Mitglieder", GRUEN_HELL)])
        l1.addWidget(self.d_klasse)
        k2, l2 = karte(18, 8)
        l2.addWidget(abschnitt_titel("Beitritte und Austritte je Jahr"))
        self.d_jahr = BalkenDiagramm([("Beitritte", GRUEN_HELL), ("Austritte", "#d9574a")])
        l2.addWidget(self.d_jahr)
        diag.addWidget(k1, 3)
        diag.addWidget(k2, 2)
        lay.addLayout(diag)

        tabs = QHBoxLayout()
        tabs.setSpacing(14)
        self.r_tabellen = []
        for titel, attr, stretch in (("Nach Klasse", "r_klasse", 3), ("Nach Jahr", "r_jahr", 2),
                                     ("Austrittsgründe im Zeitraum", "r_gruende", 2)):
            k, l = karte(18, 8)
            l.addWidget(abschnitt_titel(titel))
            t = neue_tabelle()
            t.setSortingEnabled(False)
            setattr(self, attr, t)
            self.r_tabellen.append(t)
            l.addWidget(t)
            l.addStretch()
            tabs.addWidget(k, stretch, Qt.AlignTop)
        lay.addLayout(tabs)
        lay.addStretch()
        self._revision_vorlage(0)
        return aussen

    def _revision_vorlage(self, idx):
        jahr = date.today().year
        sj = jahr if date.today().month >= 9 else jahr - 1
        bereiche = {0: (f"{jahr}-01-01", f"{jahr}-12-31"), 1: (f"{jahr - 1}-01-01", f"{jahr - 1}-12-31"),
                    2: (f"{sj}-09-01", f"{sj + 1}-08-31")}
        if idx in bereiche:
            von, bis = bereiche[idx]
            for x in (self.r_von, self.r_bis, self.r_stichtag):
                x.blockSignals(True)
            self.r_von.setDate(QDate.fromString(von, "yyyy-MM-dd"))
            self.r_bis.setDate(QDate.fromString(bis, "yyyy-MM-dd"))
            self.r_stichtag.setDate(QDate.fromString(min(bis, heute_iso()) if idx != 1 else bis, "yyyy-MM-dd"))
            for x in (self.r_von, self.r_bis, self.r_stichtag):
                x.blockSignals(False)
        self.r_von.setEnabled(idx == 3)
        self.r_bis.setEnabled(idx == 3)
        self._revision_fuellen()

    def _revision_daten(self) -> dict:
        return self.db.revision(qdate_zu_iso(self.r_stichtag.date()), qdate_zu_iso(self.r_von.date()),
                                qdate_zu_iso(self.r_bis.date()))

    def _revision_fuellen(self):
        if not hasattr(self, "rk_stand"):
            return
        rev = self._revision_daten()
        stich = iso_zu_de(rev["stichtag"])
        n_bei, n_aus = len(rev["beitritte"]), len(rev["austritte"])
        saldo = n_bei - n_aus
        self.rk_stand.setze(str(rev["anzahl_mitglieder"]), f"am {stich}\nSaldo im Zeitraum: {saldo:+d}" if saldo else f"am {stich}")
        self.rk_beginn.setze(str(rev["stand_beginn"]), f"am {iso_zu_de(rev['von'])}")
        self.rk_bei.setze(f"+{n_bei}" if n_bei else "0")
        self.rk_aus.setze(f"−{n_aus}" if n_aus else "0")
        self.rk_anteile.setze(str(rev["anteile"]))
        self.rk_guthaben.setze(euro(rev["geschaeftsguthaben"]), f"{euro(self.db.betrag_pro_anteil())} pro Anteil")
        self.rk_iban.setze(f"{rev['iban_fehlend']} / {rev['iban_ungueltig']}")

        self.d_klasse.setze([(k, [d["mitglieder"]]) for k, d in rev["pro_klasse"].items()])
        self.d_jahr.setze([(j, [d["beitritte"], d["austritte"]]) for j, d in rev["pro_jahr"].items()])

        zeilen = [[k, d["mitglieder"], d["anteile"], d["beitritte"], d["austritte"]] for k, d in rev["pro_klasse"].items()]
        if zeilen:
            zeilen.append(["Summe", sum(z[1] for z in zeilen), sum(z[2] for z in zeilen),
                           sum(z[3] for z in zeilen), sum(z[4] for z in zeilen)])
        tabelle_fuellen(self.r_klasse, ["Klasse", "Mitglieder", "Anteile", "Beitritte", "Austritte"], zeilen,
                        fett_letzte=True, rechts={1, 2, 3, 4})
        tabelle_fuellen(self.r_jahr, ["Jahr", "Beitritte", "Austritte", "Stand 31.12."],
                        [[j, d["beitritte"], d["austritte"], d["stand_ende"]] for j, d in rev["pro_jahr"].items()],
                        rechts={1, 2, 3})
        tabelle_fuellen(self.r_gruende, ["Grund", "Anzahl"],
                        sorted([[g, n] for g, n in rev["austrittsgruende"].items()], key=lambda x: -x[1]), rechts={1})
        for t in self.r_tabellen:
            h = t.horizontalHeader()
            h.setSectionResizeMode(QHeaderView.Stretch)
            h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            hoehe_an_inhalt(t)

    def _revision_exportieren(self):
        pfad = self._speichern_dialog(f"Revisionsbericht_{qdate_zu_iso(self.r_stichtag.date())}.xlsx")
        if pfad:
            excel_io.revision_exportieren(pfad, self._revision_daten(), self.db.einstellung("name"),
                                          self.db.betrag_pro_anteil())
            self._gespeichert(pfad)

    # ============================================================ Seite: Mitgliederinfo
    def _seite_info(self) -> QWidget:
        w, lay = self._seiten_rahmen()
        kopf, _ = seiten_kopf("Mitgliederinfo", "Verteiler für Einladungen und Neuigkeiten an die Mitglieder.",
                              [knopf("Verteiler als Excel", "sekundaer", self._info_export),
                               knopf("Versand protokollieren", "sekundaer", self._info_protokoll,
                                     "Trägt die Info bei allen Empfängern im Verlauf ein"),
                               knopf("E-Mail-Adressen kopieren", "primaer", self._info_kopieren)])
        lay.addWidget(kopf)
        banner = QFrame()
        banner.setObjectName("infoBanner")
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(16, 12, 16, 12)
        t = QLabel("<b>So geht’s:</b> Adressen kopieren, im E-Mail-Programm ins <b>BCC</b>-Feld einfügen (dann sehen "
                   "sich die Empfänger nicht gegenseitig) und danach „Versand protokollieren“ klicken. Dann steht die "
                   "Info bei jedem Mitglied im Verlauf.")
        t.setWordWrap(True)
        bl.addWidget(t, 1)
        bl.addWidget(knopf("E-Mail-Programm öffnen", "sekundaer", self._info_mail))
        lay.addWidget(banner)

        fk, fl = karte(14, 10)
        f = QHBoxLayout()
        f.setSpacing(12)
        self.i_klasse = QComboBox()
        self.i_klasse.setMinimumWidth(150)
        self.i_nur_info = QCheckBox("nur wer Infos erhalten möchte")
        self.i_nur_info.setChecked(True)
        self.i_angemeldet = QCheckBox("auch Mitglieder mit angemeldetem Austritt")
        self.i_angemeldet.setChecked(True)
        self.i_klasse.currentIndexChanged.connect(lambda _: self._info_fuellen())
        for x in (self.i_nur_info, self.i_angemeldet):
            x.toggled.connect(lambda _: self._info_fuellen())
        f.addWidget(QLabel("Klasse"))
        f.addWidget(self.i_klasse)
        f.addSpacing(10)
        f.addWidget(self.i_nur_info)
        f.addWidget(self.i_angemeldet)
        f.addStretch()
        fl.addLayout(f)
        lay.addWidget(fk)

        kach = QHBoxLayout()
        kach.setSpacing(14)
        self.ik_mit = Kachel("Empfänger mit E-Mail", GRUEN)
        self.ik_ohne = Kachel("Mitglieder ohne E-Mail", GELB)
        self.ik_letzte = Kachel("Letzte protokollierte Info", "#2563a8")
        self.ik_letzte.wert.setStyleSheet("color:#2563a8; font-size:12pt; font-weight:600;")
        self.ik_letzte.wert.setWordWrap(True)
        for k in (self.ik_mit, self.ik_ohne, self.ik_letzte):
            kach.addWidget(k)
        kach.setStretch(2, 2)
        lay.addLayout(kach)

        tk, tl = karte(0, 0)
        self.i_stapel = QStackedWidget()
        self.i_tabelle = neue_tabelle()
        self.i_stapel.addWidget(self.i_tabelle)
        self.i_stapel.addWidget(LeerHinweis("Keine Empfänger", "In dieser Auswahl gibt es keine aktiven Mitglieder."))
        tl.addWidget(self.i_stapel)
        lay.addWidget(tk, 1)
        return w

    def _info_empfaenger(self) -> tuple[list[Person], list[Person]]:
        kl = self.i_klasse.currentText()
        erlaubt = {STATUS_MITGLIED} | ({STATUS_AUSTRITT_ANGEMELDET} if self.i_angemeldet.isChecked() else set())
        alle = [p for p in self.personen if p.status in erlaubt
                and (not kl or kl == "Alle Klassen" or p.klasse == kl)
                and (p.info_erwuenscht or not self.i_nur_info.isChecked())]
        return [p for p in alle if p.email], [p for p in alle if not p.email]

    def _letzte_infos(self) -> dict[int, str]:
        out = {}
        for r in self.db.conn.execute("SELECT person_id, datum, beschreibung FROM ereignisse WHERE art = 'Info' "
                                      "ORDER BY datum, id"):
            out[r["person_id"]] = f"{iso_zu_de(r['datum'])} – {r['beschreibung']}"
        return out

    def _info_fuellen(self):
        mit, ohne = self._info_empfaenger()
        letzte = self._letzte_infos()
        tabelle_fuellen(self.i_tabelle, ["Nr.", "Nachname", "Vorname", "Klasse", "E-Mail", "Letzte Info"],
                        [[p.mitglieds_nr or "", p.nachname, p.vorname, p.klasse, p.email or "keine E-Mail",
                          letzte.get(p.id, "")] for p in mit + ohne])
        for r in range(self.i_tabelle.rowCount()):
            self.i_tabelle.item(r, 0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.i_tabelle.item(r, 0).setForeground(QColor(GRAU))
            if self.i_tabelle.item(r, 4).text() == "keine E-Mail":
                self.i_tabelle.item(r, 4).setForeground(QColor(ROT))
        spalten_anpassen(self.i_tabelle)
        self.i_stapel.setCurrentIndex(0 if (mit or ohne) else 1)
        self.ik_mit.setze(str(len(mit)))
        self.ik_ohne.setze(str(len(ohne)), "z. B. persönlich in der Klasse informieren" if ohne else "")
        r = self.db.conn.execute("SELECT datum, beschreibung, COUNT(*) n FROM ereignisse WHERE art = 'Info' "
                                 "GROUP BY datum, beschreibung ORDER BY datum DESC LIMIT 1").fetchone()
        if r:
            self.ik_letzte.setze(r["beschreibung"], f"am {iso_zu_de(r['datum'])} an {r['n']} Mitglieder")
        else:
            self.ik_letzte.setze("noch keine", "")

    def _info_kopieren(self):
        mit, _ = self._info_empfaenger()
        if not mit:
            QMessageBox.information(self, "Keine Empfänger", "Keine Mitglieder mit E-Mail-Adresse in dieser Auswahl.")
            return
        QApplication.clipboard().setText("; ".join(p.email for p in mit))
        self.statusBar().showMessage(f"{len(mit)} E-Mail-Adressen kopiert – im E-Mail-Programm ins BCC-Feld einfügen.", 6000)

    def _info_mail(self):
        mit, _ = self._info_empfaenger()
        if not mit:
            return
        bcc = ",".join(p.email for p in mit)
        if len(bcc) > 1800:
            QMessageBox.information(self, "Zu viele Empfänger",
                                    "Die Liste ist zu lang für einen direkten Aufruf. Die Adressen wurden kopiert – "
                                    "bitte im E-Mail-Programm ins BCC-Feld einfügen.")
            self._info_kopieren()
            return
        QDesktopServices.openUrl(QUrl(f"mailto:?bcc={bcc}&subject={self.db.einstellung('name')}"))

    def _info_protokoll(self):
        mit, _ = self._info_empfaenger()
        if not mit:
            return
        betreff, ok = QInputDialog.getText(self, "Versand protokollieren",
                                           f"Betreff der Info an {len(mit)} Mitglieder:")
        if ok and betreff.strip():
            self.db.info_protokollieren([p.id for p in mit], heute_iso(), betreff.strip())
            self.aktualisieren()
            self.statusBar().showMessage(f"Info bei {len(mit)} Mitgliedern im Verlauf eingetragen.", 5000)

    def _info_export(self):
        mit, ohne = self._info_empfaenger()
        pfad = self._speichern_dialog(f"Verteiler_{date.today():%Y-%m-%d}.xlsx")
        if pfad:
            excel_io.personen_exportieren(pfad, mit + ohne, f"{self.db.einstellung('name')} – Verteiler Mitgliederinfo",
                                          iban_voll=False)
            self._gespeichert(pfad)

    # ============================================================ Allgemein
    def aktualisieren(self):
        self.personen = self.db.alle_personen()
        name = self.db.einstellung("name")
        self.setWindowTitle(f"C.A.R.E – Mitgliederverwaltung · {name}")
        self.logo_unter.setText(f"Mitgliederverwaltung\n{name}")
        z = {s: 0 for s in ALLE_STATUS}
        for p in self.personen:
            z[p.status] += 1
        aktiv = z[STATUS_MITGLIED] + z[STATUS_AUSTRITT_ANGEMELDET]
        self.sb_zahl.setText(str(aktiv))
        self.sb_unter.setText(f"{z[STATUS_AUSTRITT_ANGEMELDET]} Austritt angemeldet · {z[STATUS_AUSGETRETEN]} ausgetreten")
        self.nav[0].setze_zahl(len(self.personen))
        self.nav[1].setze_zahl(z[STATUS_AUSGETRETEN] + z[STATUS_AUSTRITT_ANGEMELDET])
        self.nav[2].setze_zahl(None)
        self.nav[3].setze_zahl(None)
        self.p_unter.setText(f"{aktiv} Mitglieder · {z[STATUS_KEIN]} Nicht-Mitglieder · {len(self.db.klassen())} Klassen")
        klassen = ["Alle Klassen"] + self.db.klassen()
        for cb in (self.f_klasse, self.a_klasse, self.i_klasse):
            alt = cb.currentText()
            cb.blockSignals(True)
            cb.clear()
            cb.addItems(klassen)
            i = cb.findText(alt)
            cb.setCurrentIndex(i if i >= 0 else 0)
            cb.blockSignals(False)
        idx = self.stack.currentIndex() if hasattr(self, "stack") else 0
        [self._tabelle_fuellen, self._ausgetretene_fuellen, self._revision_fuellen, self._info_fuellen][idx]()

    def _zu_person_springen(self, pid: int):
        self._filter_zuruecksetzen()
        self._seite(SEITE_PERSONEN)
        for r in range(self.tabelle.rowCount()):
            if self.tabelle.item(r, 0).data(Qt.UserRole) == pid:
                self.tabelle.selectRow(r)
                self.tabelle.scrollToItem(self.tabelle.item(r, 0))
                break

    def excel_importieren(self):
        pfad, _ = QFileDialog.getOpenFileName(self, "Klassenliste importieren", str(Path.home()),
                                              "Excel / CSV (*.xlsx *.xlsm *.xls *.csv);;Alle Dateien (*)")
        if not pfad:
            return
        try:
            dlg = ImportDialog(self, self.db, pfad)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Import nicht möglich", str(e))
            return
        if dlg.exec_():
            self._seite(SEITE_PERSONEN)
            QMessageBox.information(self, "Import abgeschlossen", dlg.ergebnis_text)

    def person_neu(self):
        dlg = PersonDialog(self, self.db)
        if dlg.exec_():
            self.aktualisieren()
            self._zu_person_springen(dlg.person.id)

    def person_bearbeiten(self):
        ausw = self._ausgewaehlte()
        if len(ausw) != 1:
            return
        p = self.db.person(ausw[0].id, mit_verlauf=False)
        if PersonDialog(self, self.db, p).exec_():
            self.aktualisieren()

    def beitritt(self):
        ausw = [p for p in self._ausgewaehlte() if p.status in (STATUS_KEIN, STATUS_AUSGETRETEN)]
        if not ausw:
            QMessageBox.information(self, "Beitritt", "Bitte zuerst Personen auswählen, die noch kein Mitglied sind.")
            return
        wieder = [p for p in ausw if p.status == STATUS_AUSGETRETEN]
        if wieder and QMessageBox.question(
                self, "Wiedereintritt",
                f"{len(wieder)} der ausgewählten Personen sind bereits ausgetreten. Als Wiedereintritt erfassen?") != QMessageBox.Yes:
            ausw = [p for p in ausw if p.status != STATUS_AUSGETRETEN]
            if not ausw:
                return
        dlg = BeitrittDialog(self, self.db, ausw)
        if dlg.exec_():
            self.aktualisieren()
            self._ergebnis_melden("Beitritt", dlg.erfolgreich, dlg.fehler)

    def austritt(self):
        ausw = [p for p in self._ausgewaehlte() if p.status == STATUS_MITGLIED]
        if not ausw:
            QMessageBox.information(self, "Austritt", "Bitte zuerst Mitglieder auswählen.")
            return
        dlg = AustrittDialog(self, self.db, ausw)
        if dlg.exec_():
            self.aktualisieren()
            self._ergebnis_melden("Austritt", dlg.erfolgreich, dlg.fehler)

    def _ergebnis_melden(self, art, n, fehler):
        self.statusBar().showMessage(f"{art} für {n} Person(en) eingetragen.", 5000)
        if fehler:
            QMessageBox.warning(self, "Nicht alle eingetragen", "\n".join(fehler))

    def notiz(self):
        ausw = self._ausgewaehlte()
        if len(ausw) != 1:
            return
        text, ok = QInputDialog.getMultiLineText(self, "Notiz", f"Notiz zu {ausw[0].vorname} {ausw[0].nachname} "
                                                 "(erscheint im Verlauf):")
        if ok and text.strip():
            self.db.notiz_hinzufuegen(ausw[0].id, text.strip())
            self._detail_zeigen(ausw[0].id)

    def person_loeschen(self):
        ausw = self._ausgewaehlte()
        if not ausw:
            return
        mitglieder = [p for p in ausw if p.beitritt_datum]
        text = f"{len(ausw)} Person(en) endgültig löschen?"
        if mitglieder:
            text += (f"\n\nAchtung: {len(mitglieder)} davon sind/waren Mitglied. Für die Revision bitte "
                     "stattdessen einen Austritt erfassen – beim Löschen verschwinden sie auch aus der Statistik.")
        if QMessageBox.warning(self, "Löschen", text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            for p in ausw:
                self.db.person_loeschen(p.id)
            self.aktualisieren()

    def ansicht_exportieren(self):
        idx = self.stack.currentIndex()
        if idx == SEITE_AUSGETRETENE:
            return self._ausgetretene_exportieren()
        if idx == SEITE_REVISION:
            return self._revision_exportieren()
        if idx == SEITE_INFO:
            return self._info_export()
        liste = self._gefiltert()
        if not liste:
            QMessageBox.information(self, "Keine Daten", "Die aktuelle Ansicht ist leer.")
            return
        pfad = self._speichern_dialog(f"Personenliste_{date.today():%Y-%m-%d}.xlsx")
        if pfad:
            titel = f"{self.db.einstellung('name')} – Personenliste"
            if self.status_filter != "alle":
                titel += f" ({self.status_filter})"
            if self.f_klasse.currentIndex():
                titel += f" – Klasse {self.f_klasse.currentText()}"
            excel_io.personen_exportieren(pfad, liste, titel, iban_voll=True)
            self._gespeichert(pfad)

    def vorlage_speichern(self):
        pfad = self._speichern_dialog("CARE_Importvorlage.xlsx")
        if pfad:
            excel_io.vorlage_erstellen(pfad)
            self._gespeichert(pfad)

    def sichern(self):
        pfad = self._speichern_dialog(f"care_sicherung_{datetime.now():%Y-%m-%d_%H%M}.db", "Datenbank (*.db)")
        if pfad:
            self.db.sichern(pfad)
            self.statusBar().showMessage(f"Sicherung gespeichert: {pfad}", 6000)

    def einstellungen(self):
        if EinstellungenDialog(self, self.db).exec_():
            self.aktualisieren()

    def ueber(self):
        QMessageBox.about(self, "Über C.A.R.E",
                          "<h3>C.A.R.E – Mitgliederverwaltung</h3>"
                          f"<p>für die {html.escape(self.db.einstellung('name'))}</p>"
                          "<p>Schulprojekt BW · HBLFA Francisco Josephinum Wieselburg</p>"
                          "<p>Beitritte und Austritte, Excel-Import der Klassenlisten, IBAN-Prüfung, "
                          "Liste der Ausgetretenen und Revisionsbericht.</p>"
                          f"<p style='color:#6b766f'>Datenbank: {html.escape(str(self.db.pfad))}</p>")

    def _speichern_dialog(self, vorschlag: str, filt: str = "Excel (*.xlsx)") -> str | None:
        start = Path.home() / "Documents"
        if not start.exists():
            start = Path.home()
        pfad, _ = QFileDialog.getSaveFileName(self, "Speichern unter", str(start / vorschlag), filt)
        return pfad or None

    def _gespeichert(self, pfad: str):
        if QMessageBox.question(self, "Gespeichert", f"Gespeichert:\n{pfad}\n\nJetzt öffnen?") == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(pfad))
