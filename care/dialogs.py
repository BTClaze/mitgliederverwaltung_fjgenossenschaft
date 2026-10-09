"""Dialoge: Person bearbeiten, Beitritt, Austritt, Excel-Import, Einstellungen."""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import excel_io, iban_utils
from .database import AUSTRITTSGRUENDE, Datenbank, Person, heute_iso, iso_zu_de


def qdate_zu_iso(d: QDate) -> str:
    return d.toString("yyyy-MM-dd")


def iso_zu_qdate(iso: str | None) -> QDate:
    if not iso:
        return QDate.currentDate()
    return QDate.fromString(iso[:10], "yyyy-MM-dd")


def datum_feld(iso: str | None = None) -> QDateEdit:
    d = QDateEdit()
    d.setCalendarPopup(True)
    d.setDisplayFormat("dd.MM.yyyy")
    d.setMinimumWidth(150)
    d.setDate(iso_zu_qdate(iso or heute_iso()))
    return d


class OptionalesDatum(QWidget):
    """Datum mit Häkchen ("gesetzt / nicht gesetzt")."""

    def __init__(self, iso: str | None, text: str = ""):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.check = QCheckBox(text)
        self.datum = datum_feld(iso)
        self.check.setChecked(bool(iso))
        self.datum.setEnabled(bool(iso))
        self.check.toggled.connect(self.datum.setEnabled)
        lay.addWidget(self.check)
        lay.addWidget(self.datum, 1)

    def wert(self) -> str | None:
        return qdate_zu_iso(self.datum.date()) if self.check.isChecked() else None


class IbanFeld(QWidget):
    """IBAN-Eingabe mit Live-Prüfung."""

    def __init__(self, iban: str = ""):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.edit = QLineEdit(iban_utils.formatieren(iban))
        self.edit.setPlaceholderText("AT.. .... .... .... ....")
        self.hinweis = QLabel()
        self.hinweis.setObjectName("hinweis")
        lay.addWidget(self.edit)
        lay.addWidget(self.hinweis)
        self.edit.textChanged.connect(self._pruefen)
        self._pruefen()

    def _pruefen(self):
        text = self.edit.text()
        if not iban_utils.normalisieren(text):
            self.hinweis.setText("")
            return
        ok, msg = iban_utils.pruefen(text)
        self.hinweis.setText(("✔ " if ok else "✖ ") + msg)
        self.hinweis.setStyleSheet(f"color: {'#2e7d32' if ok else '#c62828'};")

    def wert(self) -> str:
        return iban_utils.normalisieren(self.edit.text())


# ---------------------------------------------------------------- Person
class PersonDialog(QDialog):
    def __init__(self, parent, db: Datenbank, person: Person | None = None):
        super().__init__(parent)
        self.db = db
        self.person = person or Person()
        neu = self.person.id is None
        self.setWindowTitle("Neue Person" if neu else f"{self.person.vorname} {self.person.nachname} bearbeiten")
        self.setMinimumWidth(520)
        p = self.person

        tabs = QTabWidget()
        # --- Stammdaten
        w1 = QWidget()
        f1 = QFormLayout(w1)
        self.vorname = QLineEdit(p.vorname)
        self.nachname = QLineEdit(p.nachname)
        self.klasse = QComboBox()
        self.klasse.setEditable(True)
        self.klasse.addItems([""] + db.klassen())
        self.klasse.setCurrentText(p.klasse)
        self.geburtsdatum = OptionalesDatum(p.geburtsdatum, "bekannt")
        self.email = QLineEdit(p.email)
        self.telefon = QLineEdit(p.telefon)
        self.adresse = QLineEdit(p.adresse)
        self.plz = QLineEdit(p.plz)
        self.plz.setMaximumWidth(80)
        self.ort = QLineEdit(p.ort)
        plz_ort = QHBoxLayout()
        plz_ort.addWidget(self.plz)
        plz_ort.addWidget(self.ort)
        self.info = QCheckBox("möchte Mitgliederinformationen erhalten")
        self.info.setChecked(bool(p.info_erwuenscht))
        f1.addRow("Vorname *", self.vorname)
        f1.addRow("Nachname *", self.nachname)
        f1.addRow("Klasse", self.klasse)
        f1.addRow("Geburtsdatum", self.geburtsdatum)
        f1.addRow("E-Mail", self.email)
        f1.addRow("Telefon", self.telefon)
        f1.addRow("Straße", self.adresse)
        f1.addRow("PLZ / Ort", plz_ort)
        f1.addRow("", self.info)
        tabs.addTab(w1, "Stammdaten")

        # --- Mitgliedschaft
        w2 = QWidget()
        f2 = QFormLayout(w2)
        self.nr = QSpinBox()
        self.nr.setRange(0, 999999)
        self.nr.setSpecialValueText("– automatisch –")
        self.nr.setValue(p.mitglieds_nr or 0)
        self.anteile = QSpinBox()
        self.anteile.setRange(1, 1000)
        self.anteile.setValue(p.anteile or 1)
        self.beitritt = OptionalesDatum(p.beitritt_datum, "Beitrittserklärung unterschrieben am")
        self.austritt = OptionalesDatum(p.austritt_datum, "Austrittserklärung wirksam ab")
        self.grund = QComboBox()
        self.grund.setEditable(True)
        self.grund.addItems([""] + AUSTRITTSGRUENDE)
        self.grund.setCurrentText(p.austritt_grund)
        f2.addRow("Mitglieds-Nr.", self.nr)
        f2.addRow("Geschäftsanteile", self.anteile)
        f2.addRow("Beitritt", self.beitritt)
        f2.addRow("Austritt", self.austritt)
        f2.addRow("Austrittsgrund", self.grund)
        hinweis = QLabel("Tipp: Beitritte und Austritte lassen sich auch direkt über die "
                         "Schaltflächen im Hauptfenster erfassen, auch für mehrere Personen auf einmal.")
        hinweis.setWordWrap(True)
        hinweis.setObjectName("hinweis")
        f2.addRow(hinweis)
        tabs.addTab(w2, "Mitgliedschaft")

        # --- Bank
        w3 = QWidget()
        f3 = QFormLayout(w3)
        self.iban = IbanFeld(p.iban)
        self.bic = QLineEdit(p.bic)
        self.inhaber = QLineEdit(p.kontoinhaber)
        self.inhaber.setPlaceholderText("leer = Mitglied selbst")
        f3.addRow("IBAN", self.iban)
        f3.addRow("BIC", self.bic)
        f3.addRow("Kontoinhaber", self.inhaber)
        tabs.addTab(w3, "Bankverbindung")

        # --- Notizen
        self.notizen = QPlainTextEdit(p.notizen)
        tabs.addTab(self.notizen, "Notizen")

        knoepfe = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        knoepfe.button(QDialogButtonBox.Save).setText("Speichern")
        knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self._speichern)
        knoepfe.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(knoepfe)

    def _speichern(self):
        p = self.person
        p.vorname = self.vorname.text().strip()
        p.nachname = self.nachname.text().strip()
        if not p.vorname or not p.nachname:
            QMessageBox.warning(self, "Fehlende Angaben", "Bitte Vor- und Nachname eingeben.")
            return
        iban = self.iban.wert()
        if iban and not iban_utils.ist_gueltig(iban):
            if QMessageBox.question(self, "IBAN ungültig",
                                    f"{iban_utils.pruefen(iban)[1]}.\nTrotzdem speichern?") != QMessageBox.Yes:
                return
        beitritt, austritt = self.beitritt.wert(), self.austritt.wert()
        if austritt and not beitritt:
            QMessageBox.warning(self, "Austritt ohne Beitritt", "Ein Austritt braucht ein Beitrittsdatum.")
            return
        if austritt and beitritt and austritt < beitritt:
            QMessageBox.warning(self, "Datum prüfen", "Der Austritt liegt vor dem Beitritt.")
            return
        p.klasse = self.klasse.currentText().strip()
        p.geburtsdatum = self.geburtsdatum.wert()
        p.email = self.email.text().strip()
        p.telefon = self.telefon.text().strip()
        p.adresse = self.adresse.text().strip()
        p.plz = self.plz.text().strip()
        p.ort = self.ort.text().strip()
        p.info_erwuenscht = 1 if self.info.isChecked() else 0
        p.mitglieds_nr = self.nr.value() or None
        p.anteile = self.anteile.value()
        p.beitritt_datum = beitritt
        p.austritt_datum = austritt
        p.austritt_grund = self.grund.currentText().strip() if austritt else ""
        p.iban = iban
        p.bic = self.bic.text().strip().upper()
        p.kontoinhaber = self.inhaber.text().strip()
        p.notizen = self.notizen.toPlainText().strip()
        try:
            self.db.person_speichern(p)
        except ValueError as e:
            QMessageBox.warning(self, "Speichern nicht möglich", str(e))
            return
        self.accept()


# ---------------------------------------------------------------- Beitritt
class BeitrittDialog(QDialog):
    def __init__(self, parent, db: Datenbank, personen: list[Person]):
        super().__init__(parent)
        self.db = db
        self.personen = personen
        self.setWindowTitle("Beitritt erfassen")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        namen = ", ".join(f"{p.vorname} {p.nachname}" for p in personen[:6])
        if len(personen) > 6:
            namen += f" und {len(personen) - 6} weitere"
        info = QLabel(f"<b>{len(personen)} Person(en):</b> {namen}")
        info.setWordWrap(True)
        lay.addWidget(info)
        form = QFormLayout()
        self.datum = datum_feld()
        self.anteile = QSpinBox()
        self.anteile.setRange(1, 1000)
        self.anteile.setValue(1)
        self.bemerkung = QLineEdit()
        self.bemerkung.setPlaceholderText("optional, z. B. 'Beitrittserklärung liegt im Ordner'")
        form.addRow("Beitrittserklärung vom", self.datum)
        form.addRow("Geschäftsanteile", self.anteile)
        self.iban = None
        if len(personen) == 1:
            self.iban = IbanFeld(personen[0].iban)
            form.addRow("IBAN", self.iban)
        form.addRow("Bemerkung", self.bemerkung)
        lay.addLayout(form)
        lay.addWidget(QLabel(f"Mitglieds-Nummern werden fortlaufend vergeben (nächste: {db.naechste_mitglieds_nr()})."))
        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoepfe.button(QDialogButtonBox.Ok).setText("Beitritt eintragen")
        knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self._ok)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)
        self.fehler: list[str] = []
        self.erfolgreich = 0

    def _ok(self):
        datum = qdate_zu_iso(self.datum.date())
        if self.iban is not None:
            iban = self.iban.wert()
            if iban and not iban_utils.ist_gueltig(iban):
                if QMessageBox.question(self, "IBAN ungültig", "Die IBAN ist ungültig. Trotzdem fortfahren?") != QMessageBox.Yes:
                    return
        for p in sorted(self.personen, key=lambda x: (x.nachname.lower(), x.vorname.lower())):
            try:
                self.db.beitritt_erfassen(p.id, datum, self.anteile.value(),
                                          iban=self.iban.wert() if self.iban else None,
                                          bemerkung=self.bemerkung.text().strip())
                self.erfolgreich += 1
            except ValueError as e:
                self.fehler.append(str(e))
        self.accept()


# ---------------------------------------------------------------- Austritt
class AustrittDialog(QDialog):
    def __init__(self, parent, db: Datenbank, personen: list[Person]):
        super().__init__(parent)
        self.db = db
        self.personen = personen
        self.setWindowTitle("Austritt erfassen")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        namen = ", ".join(f"{p.vorname} {p.nachname}" for p in personen[:6])
        if len(personen) > 6:
            namen += f" und {len(personen) - 6} weitere"
        info = QLabel(f"<b>{len(personen)} Person(en):</b> {namen}")
        info.setWordWrap(True)
        lay.addWidget(info)
        form = QFormLayout()
        self.datum = datum_feld()
        self.grund = QComboBox()
        self.grund.setEditable(True)
        self.grund.addItems(AUSTRITTSGRUENDE)
        self.bemerkung = QLineEdit()
        self.bemerkung.setPlaceholderText("optional")
        form.addRow("Austritt wirksam ab", self.datum)
        form.addRow("Grund", self.grund)
        form.addRow("Bemerkung", self.bemerkung)
        lay.addLayout(form)
        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoepfe.button(QDialogButtonBox.Ok).setText("Austritt eintragen")
        knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self._ok)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)
        self.fehler: list[str] = []
        self.erfolgreich = 0

    def _ok(self):
        datum = qdate_zu_iso(self.datum.date())
        for p in self.personen:
            try:
                self.db.austritt_erfassen(p.id, datum, self.grund.currentText().strip(),
                                          self.bemerkung.text().strip())
                self.erfolgreich += 1
            except ValueError as e:
                self.fehler.append(str(e))
        self.accept()


# ---------------------------------------------------------------- Import
class ImportDialog(QDialog):
    """Excel-/CSV-Import mit Spaltenzuordnung und Vorschau."""

    def __init__(self, parent, db: Datenbank, pfad: str):
        super().__init__(parent)
        self.db = db
        self.pfad = pfad
        self.setWindowTitle(f"Import – {Path(pfad).name}")
        self.resize(1000, 680)
        self.blaetter = excel_io.datei_lesen(pfad)
        if not self.blaetter:
            raise RuntimeError("Die Datei enthält keine Daten.")
        self.ergebnis_text = ""

        lay = QVBoxLayout(self)
        oben = QHBoxLayout()
        self.blatt = QComboBox()
        self.blatt.addItems(list(self.blaetter))
        self.kopfzeile = QSpinBox()
        self.kopfzeile.setMinimum(1)
        oben.addWidget(QLabel("Tabellenblatt:"))
        oben.addWidget(self.blatt)
        oben.addSpacing(20)
        oben.addWidget(QLabel("Überschriften in Zeile:"))
        oben.addWidget(self.kopfzeile)
        oben.addStretch()
        lay.addLayout(oben)

        lay.addWidget(QLabel("<b>1. Spalten zuordnen</b> – erkannt wurde automatisch, bei Bedarf ändern:"))
        self.zuordnung_tabelle = QTableWidget()
        self.zuordnung_tabelle.setFixedHeight(96)
        self.zuordnung_tabelle.verticalHeader().setDefaultSectionSize(48)
        self.zuordnung_tabelle.verticalHeader().setVisible(False)
        lay.addWidget(self.zuordnung_tabelle)

        lay.addWidget(QLabel("<b>2. Vorschau</b>"))
        self.vorschau = QTableWidget()
        self.vorschau.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.vorschau.verticalHeader().setVisible(False)
        lay.addWidget(self.vorschau, 1)
        self.status = QLabel()
        self.status.setObjectName("hinweis")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        optionen = QGroupBox("3. Optionen")
        of = QFormLayout(optionen)
        self.klasse = QLineEdit(excel_io.klasse_aus_dateiname(pfad))
        self.klasse.setPlaceholderText("z. B. 4IT – wird verwendet, wenn die Liste keine Klassenspalte hat")
        of.addRow("Klasse (falls nicht in der Liste)", self.klasse)
        self.als_liste = QRadioButton("Nur als Klassenliste übernehmen (noch keine Mitglieder)")
        self.als_mitglied = QRadioButton("Alle als Mitglieder eintragen, Beitritt am:")
        self.als_liste.setChecked(True)
        self.beitritt_datum = datum_feld()
        self.beitritt_datum.setEnabled(False)
        self.als_mitglied.toggled.connect(self.beitritt_datum.setEnabled)
        h = QHBoxLayout()
        h.addWidget(self.als_mitglied)
        h.addWidget(self.beitritt_datum)
        h.addStretch()
        of.addRow(self.als_liste)
        of.addRow(h)
        hinweis = QLabel("Hat die Liste eine Spalte \"Beitrittsdatum\", wird diese pro Person verwendet.")
        hinweis.setObjectName("hinweis")
        of.addRow(hinweis)
        self.vorhandene = QComboBox()
        self.vorhandene.addItems(["Leere Felder ergänzen und Klasse aktualisieren", "Überspringen"])
        of.addRow("Bereits vorhandene Personen", self.vorhandene)
        lay.addWidget(optionen)

        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoepfe.button(QDialogButtonBox.Ok).setText("Importieren")
        knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self._importieren)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)

        self.combos: list[QComboBox] = []
        self.blatt.currentTextChanged.connect(self._blatt_gewechselt)
        self.kopfzeile.valueChanged.connect(lambda _: self._zuordnung_aufbauen())
        self.klasse.textChanged.connect(lambda _: self._vorschau_aktualisieren())
        self._blatt_gewechselt(self.blatt.currentText())

    def _zeilen(self):
        return self.blaetter[self.blatt.currentText()]

    def _blatt_gewechselt(self, _):
        z = self._zeilen()
        self.kopfzeile.blockSignals(True)
        self.kopfzeile.setMaximum(max(1, len(z)))
        self.kopfzeile.setValue(excel_io.kopfzeile_finden(z) + 1)
        self.kopfzeile.blockSignals(False)
        if not self.klasse.text():
            self.klasse.setText(excel_io.klasse_aus_dateiname(self.blatt.currentText()))
        self._zuordnung_aufbauen()

    def _zuordnung_aufbauen(self):
        z = self._zeilen()
        kopf = z[self.kopfzeile.value() - 1] if z else []
        vorschlag = excel_io.zuordnung_vorschlagen(kopf)
        t = self.zuordnung_tabelle
        t.clear()
        t.setColumnCount(len(kopf))
        t.setRowCount(1)
        t.setHorizontalHeaderLabels([str(k) if k not in (None, "") else f"Spalte {i + 1}" for i, k in enumerate(kopf)])
        self.combos = []
        felder = list(excel_io.IMPORT_FELDER.items())
        for i, f in enumerate(vorschlag):
            cb = QComboBox()
            cb.addItem(excel_io.NICHT_IMPORTIEREN, None)
            for key, (anzeige, _) in felder:
                cb.addItem(anzeige, key)
            if f:
                cb.setCurrentIndex(cb.findData(f))
            cb.currentIndexChanged.connect(lambda _: self._vorschau_aktualisieren())
            t.setCellWidget(0, i, cb)
            self.combos.append(cb)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setMinimumSectionSize(150)
        self._vorschau_aktualisieren()

    def _personen(self):
        zuordnung = [cb.currentData() for cb in self.combos]
        return excel_io.zeilen_zu_personen(self._zeilen(), self.kopfzeile.value() - 1, zuordnung,
                                           self.klasse.text().strip())

    def _vorschau_aktualisieren(self):
        zuordnung = [cb.currentData() for cb in self.combos]
        doppelt = {f for f in zuordnung if f and zuordnung.count(f) > 1}
        personen, warnungen = self._personen()
        spalten = ["Nachname", "Vorname", "Klasse", "Geburtsdatum", "E-Mail", "IBAN", "Beitritt", "Bereits vorhanden?"]
        v = self.vorschau
        v.clear()
        v.setColumnCount(len(spalten))
        v.setHorizontalHeaderLabels(spalten)
        v.setRowCount(min(len(personen), 200))
        vorhanden = 0
        for r, p in enumerate(personen):
            dup = self.db.suche_duplikat(p.vorname, p.nachname, p.geburtsdatum)
            vorhanden += 1 if dup else 0
            if r >= 200:
                continue
            werte = [p.nachname, p.vorname, p.klasse, iso_zu_de(p.geburtsdatum), p.email,
                     iban_utils.maskieren(p.iban), iso_zu_de(p.beitritt_datum), "ja" if dup else ""]
            for c, w in enumerate(werte):
                v.setItem(r, c, QTableWidgetItem(str(w)))
        v.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        text = f"{len(personen)} Personen erkannt, davon {vorhanden} bereits in der Datenbank."
        if not any(f in zuordnung for f in ("vorname", "nachname", "name_nv", "name_vn")):
            text = "⚠ Bitte mindestens die Spalten für Vor- und Nachname (oder Name komplett) zuordnen."
        if doppelt:
            text += "  ⚠ Ein Zielfeld ist mehrfach zugeordnet."
        if warnungen:
            text += f"\n{len(warnungen)} Hinweis(e): " + "; ".join(warnungen[:4]) + (" …" if len(warnungen) > 4 else "")
        self.status.setText(text)

    def _importieren(self):
        personen, warnungen = self._personen()
        if not personen:
            QMessageBox.warning(self, "Nichts zu importieren", "Es wurden keine Personen erkannt.")
            return
        als_mitglied = self.als_mitglied.isChecked()
        beitritt = qdate_zu_iso(self.beitritt_datum.date())
        ergaenzen = self.vorhandene.currentIndex() == 0
        neu = aktualisiert = uebersprungen = 0
        fehler = []
        quelle = Path(self.pfad).name
        for p in personen:
            if als_mitglied and not p.beitritt_datum:
                p.beitritt_datum = beitritt
            dup = self.db.suche_duplikat(p.vorname, p.nachname, p.geburtsdatum)
            try:
                if dup is None:
                    if p.mitglieds_nr and not self.db.mitglieds_nr_frei(p.mitglieds_nr):
                        p.mitglieds_nr = None
                    self.db.person_speichern(p, protokoll=f"Import aus {quelle}")
                    neu += 1
                elif ergaenzen:
                    geaendert = False
                    for f in ("klasse", "geburtsdatum", "email", "telefon", "adresse", "plz", "ort",
                              "iban", "bic", "kontoinhaber"):
                        nw = getattr(p, f)
                        if nw and (f == "klasse" or not getattr(dup, f)) and getattr(dup, f) != nw:
                            setattr(dup, f, nw)
                            geaendert = True
                    if geaendert:
                        self.db.person_speichern(dup, protokoll=f"Aktualisiert durch Import aus {quelle}")
                    if p.beitritt_datum and not dup.beitritt_datum:
                        self.db.beitritt_erfassen(dup.id, p.beitritt_datum, p.anteile or 1)
                        geaendert = True
                    aktualisiert += 1 if geaendert else 0
                    uebersprungen += 0 if geaendert else 1
                else:
                    uebersprungen += 1
            except ValueError as e:
                fehler.append(f"{p.vorname} {p.nachname}: {e}")
        self.ergebnis_text = (f"{neu} neu angelegt, {aktualisiert} aktualisiert, {uebersprungen} unverändert/übersprungen.")
        if fehler:
            self.ergebnis_text += "\n\nFehler:\n" + "\n".join(fehler[:15])
        if warnungen:
            self.ergebnis_text += "\n\nHinweise:\n" + "\n".join(warnungen[:15])
        self.accept()


# ---------------------------------------------------------------- Einstellungen
class EinstellungenDialog(QDialog):
    def __init__(self, parent, db: Datenbank):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Einstellungen")
        form = QFormLayout(self)
        self.name = QLineEdit(db.einstellung("name"))
        self.betrag = QLineEdit(db.einstellung("betrag_pro_anteil").replace(".", ","))
        form.addRow("Name der Genossenschaft", self.name)
        form.addRow("Betrag pro Geschäftsanteil (€)", self.betrag)
        knoepfe = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        knoepfe.accepted.connect(self._ok)
        knoepfe.rejected.connect(self.reject)
        form.addRow(knoepfe)

    def _ok(self):
        try:
            betrag = float(self.betrag.text().replace(",", ".") or 0)
        except ValueError:
            QMessageBox.warning(self, "Betrag", "Bitte einen Betrag wie 10,00 eingeben.")
            return
        self.db.einstellung_setzen("name", self.name.text().strip() or "FJ Genossenschaft")
        self.db.einstellung_setzen("betrag_pro_anteil", f"{betrag:.2f}")
        self.accept()
