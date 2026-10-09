"""SQLite-Datenbank für die Mitgliederverwaltung der FJ Genossenschaft.

Tabellen
--------
personen      aktueller Stand jeder Person (Stammdaten, Bankdaten, Mitgliedschaft)
ereignisse    Verlauf: Beitritt, Austritt, Änderung, Info, Import, ...
              -> Beitritte/Austritte für die Revision werden hieraus gezählt,
                 damit auch Wiedereintritte korrekt erfasst sind.
einstellungen Schlüssel/Wert (Name der Genossenschaft, Betrag pro Anteil, ...)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import iban_utils

STATUS_KEIN = "Kein Mitglied"
STATUS_MITGLIED = "Mitglied"
STATUS_AUSTRITT_ANGEMELDET = "Austritt angemeldet"
STATUS_AUSGETRETEN = "Ausgetreten"
ALLE_STATUS = [STATUS_MITGLIED, STATUS_AUSTRITT_ANGEMELDET, STATUS_AUSGETRETEN, STATUS_KEIN]

AUSTRITTSGRUENDE = [
    "Schulabschluss",
    "Schulwechsel / Schulabbruch",
    "Kündigung durch Mitglied",
    "Ausschluss",
    "Sonstiges",
]

PERSON_FELDER = [
    "mitglieds_nr", "vorname", "nachname", "klasse", "geburtsdatum", "email",
    "telefon", "adresse", "plz", "ort", "iban", "bic", "kontoinhaber",
    "anteile", "beitritt_datum", "austritt_datum", "austritt_grund",
    "info_erwuenscht", "notizen",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS personen (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mitglieds_nr    INTEGER,
    vorname         TEXT NOT NULL,
    nachname        TEXT NOT NULL,
    klasse          TEXT,
    geburtsdatum    TEXT,
    email           TEXT,
    telefon         TEXT,
    adresse         TEXT,
    plz             TEXT,
    ort             TEXT,
    iban            TEXT,
    bic             TEXT,
    kontoinhaber    TEXT,
    anteile         INTEGER DEFAULT 1,
    beitritt_datum  TEXT,
    austritt_datum  TEXT,
    austritt_grund  TEXT,
    info_erwuenscht INTEGER DEFAULT 1,
    notizen         TEXT,
    erstellt_am     TEXT DEFAULT (datetime('now','localtime')),
    geaendert_am    TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_personen_nr ON personen(mitglieds_nr) WHERE mitglieds_nr IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_personen_name ON personen(nachname, vorname);

CREATE TABLE IF NOT EXISTS ereignisse (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id    INTEGER NOT NULL REFERENCES personen(id) ON DELETE CASCADE,
    datum        TEXT NOT NULL,
    art          TEXT NOT NULL,
    beschreibung TEXT,
    grund        TEXT,
    erstellt_am  TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_ereignisse_person ON ereignisse(person_id);

CREATE TABLE IF NOT EXISTS einstellungen (
    schluessel TEXT PRIMARY KEY,
    wert       TEXT
);
"""

STANDARD_EINSTELLUNGEN = {
    "name": "FJ Genossenschaft",
    "betrag_pro_anteil": "10.00",
}


# ---------------------------------------------------------------- Datum
def heute_iso() -> str:
    return date.today().isoformat()


def iso_zu_de(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso


def de_zu_iso(text: str | None) -> str | None:
    """Akzeptiert 01.09.2025, 1.9.25, 2025-09-01, datetime/date-Objekte."""
    if text is None:
        return None
    if isinstance(text, datetime):
        return text.date().isoformat()
    if isinstance(text, date):
        return text.isoformat()
    text = str(text).strip()
    if not text:
        return None
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- Person
@dataclass
class Person:
    id: int | None = None
    mitglieds_nr: int | None = None
    vorname: str = ""
    nachname: str = ""
    klasse: str = ""
    geburtsdatum: str | None = None
    email: str = ""
    telefon: str = ""
    adresse: str = ""
    plz: str = ""
    ort: str = ""
    iban: str = ""
    bic: str = ""
    kontoinhaber: str = ""
    anteile: int = 1
    beitritt_datum: str | None = None
    austritt_datum: str | None = None
    austritt_grund: str = ""
    info_erwuenscht: int = 1
    notizen: str = ""
    erstellt_am: str | None = None
    geaendert_am: str | None = None
    ereignisse: list = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.nachname} {self.vorname}".strip()

    @property
    def status(self) -> str:
        return status_am(self.beitritt_datum, self.austritt_datum, heute_iso())

    @property
    def iban_gueltig(self) -> bool:
        return iban_utils.ist_gueltig(self.iban)


def status_am(beitritt: str | None, austritt: str | None, stichtag: str) -> str:
    if not beitritt:
        return STATUS_KEIN
    if beitritt > stichtag:
        return STATUS_KEIN
    if austritt:
        return STATUS_AUSGETRETEN if austritt <= stichtag else STATUS_AUSTRITT_ANGEMELDET
    return STATUS_MITGLIED


# ---------------------------------------------------------------- Datenbank
class Datenbank:
    def __init__(self, pfad: str | Path):
        self.pfad = Path(pfad)
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.pfad))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        for k, v in STANDARD_EINSTELLUNGEN.items():
            self.conn.execute(
                "INSERT OR IGNORE INTO einstellungen(schluessel, wert) VALUES (?, ?)", (k, v))
        self.conn.commit()

    def schliessen(self):
        self.conn.close()

    # ------------------------------------------------ Einstellungen
    def einstellung(self, schluessel: str, standard: str = "") -> str:
        row = self.conn.execute(
            "SELECT wert FROM einstellungen WHERE schluessel = ?", (schluessel,)).fetchone()
        return row["wert"] if row and row["wert"] is not None else standard

    def einstellung_setzen(self, schluessel: str, wert: str):
        self.conn.execute(
            "INSERT INTO einstellungen(schluessel, wert) VALUES (?, ?) "
            "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (schluessel, wert))
        self.conn.commit()

    def betrag_pro_anteil(self) -> float:
        try:
            return float(self.einstellung("betrag_pro_anteil", "10").replace(",", "."))
        except ValueError:
            return 0.0

    # ------------------------------------------------ Lesen
    @staticmethod
    def _zu_person(row: sqlite3.Row) -> Person:
        d = dict(row)
        d.pop("ereignisse", None)
        p = Person(**{k: d[k] for k in d if k in Person.__dataclass_fields__})
        for k in ("vorname", "nachname", "klasse", "email", "telefon", "adresse", "plz",
                  "ort", "iban", "bic", "kontoinhaber", "austritt_grund", "notizen"):
            if getattr(p, k) is None:
                setattr(p, k, "")
        if p.anteile is None:
            p.anteile = 1
        return p

    def alle_personen(self) -> list[Person]:
        rows = self.conn.execute(
            "SELECT * FROM personen ORDER BY nachname COLLATE NOCASE, vorname COLLATE NOCASE")
        return [self._zu_person(r) for r in rows]

    def person(self, pid: int, mit_verlauf: bool = True) -> Person | None:
        row = self.conn.execute("SELECT * FROM personen WHERE id = ?", (pid,)).fetchone()
        if not row:
            return None
        p = self._zu_person(row)
        if mit_verlauf:
            p.ereignisse = [dict(r) for r in self.conn.execute(
                "SELECT * FROM ereignisse WHERE person_id = ? ORDER BY datum DESC, id DESC", (pid,))]
        return p

    def klassen(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT klasse FROM personen WHERE klasse IS NOT NULL AND klasse <> '' "
            "ORDER BY klasse COLLATE NOCASE")
        return [r["klasse"] for r in rows]

    def suche_duplikat(self, vorname: str, nachname: str, geburtsdatum: str | None = None) -> Person | None:
        rows = self.conn.execute(
            "SELECT * FROM personen WHERE lower(trim(vorname)) = lower(trim(?)) "
            "AND lower(trim(nachname)) = lower(trim(?))", (vorname, nachname)).fetchall()
        for r in rows:
            if geburtsdatum and r["geburtsdatum"] and r["geburtsdatum"] != geburtsdatum:
                continue
            return self._zu_person(r)
        return None

    def naechste_mitglieds_nr(self) -> int:
        row = self.conn.execute("SELECT MAX(mitglieds_nr) AS m FROM personen").fetchone()
        return (row["m"] or 0) + 1

    def mitglieds_nr_frei(self, nr: int, ausser_id: int | None = None) -> bool:
        row = self.conn.execute(
            "SELECT id FROM personen WHERE mitglieds_nr = ? AND id IS NOT ?", (nr, ausser_id)).fetchone()
        return row is None

    # ------------------------------------------------ Schreiben
    def _ereignis(self, pid: int, datum: str, art: str, beschreibung: str = "", grund: str | None = None):
        self.conn.execute(
            "INSERT INTO ereignisse(person_id, datum, art, beschreibung, grund) VALUES (?, ?, ?, ?, ?)",
            (pid, datum or heute_iso(), art, beschreibung, grund))

    def person_speichern(self, p: Person, protokoll: str | None = None) -> int:
        """Neu anlegen (p.id is None) oder aktualisieren. Gibt die ID zurück."""
        p.iban = iban_utils.normalisieren(p.iban)
        if p.id is None and p.beitritt_datum and not p.mitglieds_nr:
            p.mitglieds_nr = self.naechste_mitglieds_nr()
        if p.mitglieds_nr and not self.mitglieds_nr_frei(p.mitglieds_nr, p.id):
            raise ValueError(f"Mitglieds-Nr. {p.mitglieds_nr} ist schon vergeben.")
        werte = [getattr(p, f) for f in PERSON_FELDER]
        jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if p.id is None:
            cur = self.conn.execute(
                f"INSERT INTO personen({', '.join(PERSON_FELDER)}) "
                f"VALUES ({', '.join('?' * len(PERSON_FELDER))})", werte)
            p.id = cur.lastrowid
            self._ereignis(p.id, heute_iso(), "Angelegt", protokoll or "Person angelegt")
            if p.beitritt_datum:
                self._ereignis(p.id, p.beitritt_datum, "Beitritt",
                               f"Beitrittserklärung, {p.anteile} Anteil(e)")
            if p.austritt_datum:
                self._ereignis(p.id, p.austritt_datum, "Austritt", p.austritt_grund or "", p.austritt_grund)
        else:
            alt = self.person(p.id, mit_verlauf=False)
            self.conn.execute(
                f"UPDATE personen SET {', '.join(f + ' = ?' for f in PERSON_FELDER)}, "
                f"geaendert_am = ? WHERE id = ?", werte + [jetzt, p.id])
            if alt:
                self._aenderungen_protokollieren(alt, p, protokoll)
        self.conn.commit()
        return p.id

    def _aenderungen_protokollieren(self, alt: Person, neu: Person, protokoll: str | None):
        geaendert = []
        for f in PERSON_FELDER:
            a, n = getattr(alt, f), getattr(neu, f)
            if (a or "") != (n or "") and f not in ("beitritt_datum", "austritt_datum", "austritt_grund"):
                geaendert.append("IBAN" if f == "iban" else f.replace("_", " ").capitalize())
        # Beitritt/Austritt manuell im Bearbeiten-Dialog geändert
        if (alt.beitritt_datum or "") != (neu.beitritt_datum or ""):
            if alt.beitritt_datum:
                self.conn.execute(
                    "DELETE FROM ereignisse WHERE person_id = ? AND art = 'Beitritt' AND datum = ?",
                    (neu.id, alt.beitritt_datum))
            if neu.beitritt_datum:
                self._ereignis(neu.id, neu.beitritt_datum, "Beitritt",
                               "Beitrittsdatum korrigiert" if alt.beitritt_datum else "Beitrittserklärung")
                if not neu.mitglieds_nr:
                    neu.mitglieds_nr = self.naechste_mitglieds_nr()
                    self.conn.execute("UPDATE personen SET mitglieds_nr = ? WHERE id = ?",
                                      (neu.mitglieds_nr, neu.id))
        if (alt.austritt_datum or "") != (neu.austritt_datum or ""):
            if neu.austritt_datum:
                if alt.austritt_datum:
                    self.conn.execute(
                        "DELETE FROM ereignisse WHERE person_id = ? AND art = 'Austritt' AND datum = ?",
                        (neu.id, alt.austritt_datum))
                self._ereignis(neu.id, neu.austritt_datum, "Austritt", neu.austritt_grund or "", neu.austritt_grund)
            else:
                self.conn.execute(
                    "DELETE FROM ereignisse WHERE person_id = ? AND art = 'Austritt' AND datum = ?",
                    (neu.id, alt.austritt_datum))
                self._ereignis(neu.id, heute_iso(), "Änderung", "Austritt zurückgenommen")
        if geaendert:
            self._ereignis(neu.id, heute_iso(), "Änderung",
                           protokoll or "Geändert: " + ", ".join(geaendert))

    def beitritt_erfassen(self, pid: int, datum: str, anteile: int = 1,
                          mitglieds_nr: int | None = None, iban: str | None = None,
                          bemerkung: str = "") -> None:
        p = self.person(pid, mit_verlauf=False)
        if p is None:
            return
        if p.status in (STATUS_MITGLIED, STATUS_AUSTRITT_ANGEMELDET):
            raise ValueError(f"{p.name} ist bereits Mitglied.")
        wieder = p.status == STATUS_AUSGETRETEN
        if mitglieds_nr is None:
            mitglieds_nr = p.mitglieds_nr or self.naechste_mitglieds_nr()
        elif not self.mitglieds_nr_frei(mitglieds_nr, pid):
            raise ValueError(f"Mitglieds-Nr. {mitglieds_nr} ist schon vergeben.")
        neue_iban = iban_utils.normalisieren(iban) if iban else p.iban
        self.conn.execute(
            "UPDATE personen SET beitritt_datum = ?, austritt_datum = NULL, austritt_grund = NULL, "
            "anteile = ?, mitglieds_nr = ?, iban = ?, geaendert_am = datetime('now','localtime') "
            "WHERE id = ?", (datum, anteile, mitglieds_nr, neue_iban, pid))
        text = ("Wiedereintritt" if wieder else "Beitrittserklärung") + f", {anteile} Anteil(e)"
        if bemerkung:
            text += f" – {bemerkung}"
        self._ereignis(pid, datum, "Beitritt", text)
        self.conn.commit()

    def austritt_erfassen(self, pid: int, datum: str, grund: str, bemerkung: str = "") -> None:
        p = self.person(pid, mit_verlauf=False)
        if p is None:
            return
        if not p.beitritt_datum or p.status == STATUS_KEIN:
            raise ValueError(f"{p.name} ist kein Mitglied.")
        if p.austritt_datum:
            raise ValueError(f"Für {p.name} ist bereits ein Austritt eingetragen.")
        if datum < p.beitritt_datum:
            raise ValueError(f"Austritt von {p.name} liegt vor dem Beitritt.")
        self.conn.execute(
            "UPDATE personen SET austritt_datum = ?, austritt_grund = ?, "
            "geaendert_am = datetime('now','localtime') WHERE id = ?", (datum, grund, pid))
        text = f"Austrittserklärung – {grund}" + (f" ({bemerkung})" if bemerkung else "")
        self._ereignis(pid, datum, "Austritt", text, grund)
        self.conn.commit()

    def info_protokollieren(self, pids: list[int], datum: str, betreff: str):
        for pid in pids:
            self._ereignis(pid, datum, "Info", betreff)
        self.conn.commit()

    def notiz_hinzufuegen(self, pid: int, text: str):
        self._ereignis(pid, heute_iso(), "Notiz", text)
        self.conn.commit()

    def person_loeschen(self, pid: int):
        self.conn.execute("DELETE FROM personen WHERE id = ?", (pid,))
        self.conn.commit()

    # ------------------------------------------------ Auswertungen / Revision
    def ereignisse_art(self, art: str, von: str, bis: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT p.*, e.datum, e.beschreibung, e.grund AS ereignis_grund FROM ereignisse e JOIN personen p ON p.id = e.person_id "
            "WHERE e.art = ? AND e.datum BETWEEN ? AND ? ORDER BY e.datum, p.nachname", (art, von, bis))
        return [dict(r) for r in rows]

    def mitglieder_am(self, stichtag: str) -> list[Person]:
        """Alle Personen, die am Stichtag Mitglied waren (auf Basis des Verlaufs)."""
        ergebnis = []
        verlauf: dict[int, list[tuple[str, str]]] = {}
        for r in self.conn.execute(
                "SELECT person_id, datum, art FROM ereignisse WHERE art IN ('Beitritt','Austritt') "
                "AND datum <= ? ORDER BY datum, CASE art WHEN 'Beitritt' THEN 0 ELSE 1 END, id",
                (stichtag,)):
            verlauf.setdefault(r["person_id"], []).append((r["datum"], r["art"]))
        for pid, evs in verlauf.items():
            letzter_datum, letzte_art = evs[-1]
            # Austritt wirkt ab dem Austrittsdatum -> am Austrittstag selbst kein Mitglied mehr
            if letzte_art == "Beitritt":
                p = self.person(pid, mit_verlauf=False)
                if p:
                    ergebnis.append(p)
        ergebnis.sort(key=lambda p: (p.nachname.lower(), p.vorname.lower()))
        return ergebnis

    def revision(self, stichtag: str, von: str, bis: str) -> dict:
        mitglieder = self.mitglieder_am(stichtag)
        beitritte = self.ereignisse_art("Beitritt", von, bis)
        austritte = self.ereignisse_art("Austritt", von, bis)
        stand_beginn = len(self.mitglieder_am(_tag_davor(von)))
        anteile = sum(p.anteile or 0 for p in mitglieder)

        pro_klasse: dict[str, dict] = {}

        def k(name):
            return pro_klasse.setdefault(name or "(ohne Klasse)",
                                         {"mitglieder": 0, "anteile": 0, "beitritte": 0, "austritte": 0})
        for p in mitglieder:
            k(p.klasse)["mitglieder"] += 1
            k(p.klasse)["anteile"] += p.anteile or 0
        for b in beitritte:
            k(b["klasse"])["beitritte"] += 1
        for a in austritte:
            k(a["klasse"])["austritte"] += 1

        pro_jahr: dict[str, dict] = {}
        for r in self.conn.execute(
                "SELECT substr(datum,1,4) AS jahr, art, COUNT(*) AS n FROM ereignisse "
                "WHERE art IN ('Beitritt','Austritt') GROUP BY jahr, art ORDER BY jahr"):
            d = pro_jahr.setdefault(r["jahr"], {"beitritte": 0, "austritte": 0})
            d["beitritte" if r["art"] == "Beitritt" else "austritte"] = r["n"]
        for jahr in pro_jahr:
            pro_jahr[jahr]["stand_ende"] = len(self.mitglieder_am(f"{jahr}-12-31"))

        gruende: dict[str, int] = {}
        for a in austritte:
            g = a.get("ereignis_grund") or "(kein Grund)"
            gruende[g] = gruende.get(g, 0) + 1

        return {
            "stichtag": stichtag, "von": von, "bis": bis,
            "mitglieder": mitglieder,
            "anzahl_mitglieder": len(mitglieder),
            "stand_beginn": stand_beginn,
            "beitritte": beitritte, "austritte": austritte,
            "anteile": anteile,
            "geschaeftsguthaben": anteile * self.betrag_pro_anteil(),
            "pro_klasse": dict(sorted(pro_klasse.items(), key=lambda x: x[0].lower())),
            "pro_jahr": pro_jahr,
            "austrittsgruende": gruende,
            "iban_fehlend": sum(1 for p in mitglieder if not p.iban),
            "iban_ungueltig": sum(1 for p in mitglieder if p.iban and not p.iban_gueltig),
        }

    # ------------------------------------------------ Sicherung
    def sichern(self, ziel: str | Path):
        self.conn.commit()
        bak = sqlite3.connect(str(ziel))
        with bak:
            self.conn.backup(bak)
        bak.close()


def _tag_davor(iso: str) -> str:
    from datetime import timedelta
    return (datetime.strptime(iso, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
