"""Excel-Import (Klassenlisten) und Excel-Export (Listen, Revisionsbericht)."""
from __future__ import annotations

import csv
import re
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import iban_utils
from .database import Person, de_zu_iso, iso_zu_de

# Zielfelder beim Import: Schlüssel -> (Anzeigename, Suchbegriffe für die Spaltenerkennung)
IMPORT_FELDER = {
    "vorname": ("Vorname", ["vorname", "first name", "firstname", "vname", "rufname"]),
    "nachname": ("Nachname", ["nachname", "familienname", "zuname", "last name", "lastname", "surname"]),
    "name_nv": ("Name komplett (Nachname Vorname)", ["name", "schüler", "schueler", "schülerin", "schüler/in"]),
    "name_vn": ("Name komplett (Vorname Nachname)", []),
    "klasse": ("Klasse", ["klasse", "class", "kl.", "kl", "jahrgang"]),
    "geburtsdatum": ("Geburtsdatum", ["geburtsdatum", "geb.datum", "gebdat", "geb.", "geboren", "geburtstag", "birth"]),
    "email": ("E-Mail", ["e-mail", "email", "mail", "e-mail-adresse"]),
    "telefon": ("Telefon", ["telefon", "tel", "handy", "mobil", "phone"]),
    "adresse": ("Straße / Adresse", ["adresse", "straße", "strasse", "anschrift", "str."]),
    "plz": ("PLZ", ["plz", "postleitzahl", "zip"]),
    "ort": ("Ort", ["ort", "wohnort", "stadt", "city"]),
    "iban": ("IBAN", ["iban", "kontonummer", "konto"]),
    "bic": ("BIC", ["bic", "swift"]),
    "kontoinhaber": ("Kontoinhaber", ["kontoinhaber", "inhaber"]),
    "anteile": ("Anteile", ["anteile", "anteil", "geschäftsanteile"]),
    "beitritt_datum": ("Beitrittsdatum", ["beitritt", "beitrittsdatum", "eintritt", "eintrittsdatum"]),
    "austritt_datum": ("Austrittsdatum", ["austritt", "austrittsdatum"]),
    "mitglieds_nr": ("Mitglieds-Nr.", ["mitglieds-nr", "mitgliedsnr", "mitgliedsnummer", "mitglied nr", "mitglieds nr"]),
    "notizen": ("Notizen", ["notiz", "notizen", "bemerkung", "anmerkung"]),
}
NICHT_IMPORTIEREN = "— nicht importieren —"


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


# ---------------------------------------------------------------- Lesen
def datei_lesen(pfad: str | Path) -> dict[str, list[list]]:
    """Liest alle Tabellenblätter einer Datei. Rückgabe: {Blattname: Zeilen}."""
    pfad = Path(pfad)
    endung = pfad.suffix.lower()
    if endung in (".xlsx", ".xlsm"):
        wb = load_workbook(pfad, data_only=True, read_only=True)
        blaetter = {}
        for ws in wb.worksheets:
            zeilen = [list(r) for r in ws.iter_rows(values_only=True)]
            zeilen = [z for z in zeilen if any(c not in (None, "") for c in z)]
            if zeilen:
                blaetter[ws.title] = zeilen
        wb.close()
        return blaetter
    if endung == ".xls":
        try:
            import xlrd  # optional
        except ImportError as e:
            raise RuntimeError("Alte .xls-Dateien bitte in Excel als .xlsx speichern "
                               "(oder 'pip install xlrd').") from e
        book = xlrd.open_workbook(str(pfad))
        blaetter = {}
        for sh in book.sheets():
            zeilen = []
            for i in range(sh.nrows):
                z = []
                for c in sh.row(i):
                    if c.ctype == xlrd.XL_CELL_DATE:
                        z.append(xlrd.xldate.xldate_as_datetime(c.value, book.datemode))
                    else:
                        z.append(c.value)
                if any(v not in (None, "") for v in z):
                    zeilen.append(z)
            if zeilen:
                blaetter[sh.name] = zeilen
        return blaetter
    if endung in (".csv", ".txt"):
        roh = pfad.read_bytes()
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = roh.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        dialekt = csv.Sniffer().sniff(text[:4096], delimiters=";,\t") if text.strip() else csv.excel
        zeilen = [z for z in csv.reader(text.splitlines(), dialekt) if any(c.strip() for c in z)]
        return {pfad.stem: zeilen}
    raise RuntimeError(f"Dateityp {endung} wird nicht unterstützt (xlsx, xls, csv).")


def kopfzeile_finden(zeilen: list[list]) -> int:
    """Sucht in den ersten 15 Zeilen die Zeile mit den meisten bekannten Spaltennamen."""
    beste, bester_wert = 0, -1
    for i, z in enumerate(zeilen[:15]):
        wert = sum(1 for c in z if _feld_fuer_spalte(c) is not None)
        if wert > bester_wert:
            beste, bester_wert = i, wert
    return beste


def _feld_fuer_spalte(kopf) -> str | None:
    k = _norm(kopf)
    if not k:
        return None
    # 1. exakter Treffer
    for feld, (anzeige, begriffe) in IMPORT_FELDER.items():
        if k == anzeige.lower() or k in begriffe:
            return feld
    # 2. Teiltreffer (längere Begriffe zuerst, "name" nur exakt)
    kandidaten = []
    for feld, (_, begriffe) in IMPORT_FELDER.items():
        for b in begriffe:
            if len(b) >= 4 and b in k:
                kandidaten.append((len(b), feld))
    if kandidaten:
        return max(kandidaten)[1]
    return None


def zuordnung_vorschlagen(kopf: list) -> list[str | None]:
    """Für jede Spalte das vermutete Zielfeld (oder None)."""
    vergeben = set()
    ergebnis = []
    for c in kopf:
        f = _feld_fuer_spalte(c)
        if f in vergeben:
            f = None
        if f:
            vergeben.add(f)
        ergebnis.append(f)
    # Gibt es Vor- und Nachname getrennt, wird "Name" nicht als Komplettname verwendet
    if "vorname" in vergeben and "nachname" in vergeben:
        ergebnis = [None if f == "name_nv" else f for f in ergebnis]
    elif "vorname" in vergeben and "name_nv" in vergeben:
        ergebnis = ["nachname" if f == "name_nv" else f for f in ergebnis]
    return ergebnis


def klasse_aus_dateiname(name: str) -> str:
    """'Klassenliste_4IT_2025.xlsx' -> '4IT' (wenn erkennbar)."""
    m = re.search(r"(?<![A-Za-z0-9])(\d{1,2}\s?[A-Za-z]{1,4})(?![A-Za-z])", Path(name).stem)
    return m.group(1).replace(" ", "").upper() if m else ""


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def zeilen_zu_personen(zeilen: list[list], kopf_index: int, zuordnung: list[str | None],
                       standard_klasse: str = "") -> tuple[list[Person], list[str]]:
    """Wandelt die Datenzeilen anhand der Spaltenzuordnung in Person-Objekte um."""
    personen, warnungen = [], []
    for nr, z in enumerate(zeilen[kopf_index + 1:], start=kopf_index + 2):
        werte: dict[str, object] = {}
        for i, feld in enumerate(zuordnung):
            if feld and i < len(z):
                werte[feld] = z[i]
        p = Person()
        if "name_nv" in werte or "name_vn" in werte:
            teile = _text(werte.get("name_nv") or werte.get("name_vn")).split()
            if teile:
                if "name_nv" in werte:
                    p.nachname, p.vorname = teile[0], " ".join(teile[1:])
                else:
                    p.vorname, p.nachname = " ".join(teile[:-1]), teile[-1]
        if "vorname" in werte:
            p.vorname = _text(werte["vorname"])
        if "nachname" in werte:
            p.nachname = _text(werte["nachname"])
        if not p.vorname and not p.nachname:
            continue
        if not p.vorname or not p.nachname:
            warnungen.append(f"Zeile {nr}: Vor- oder Nachname fehlt ({p.vorname or p.nachname})")
        for f in ("klasse", "email", "telefon", "adresse", "plz", "ort", "bic", "kontoinhaber", "notizen"):
            if f in werte:
                setattr(p, f, _text(werte[f]))
        if not p.klasse:
            p.klasse = standard_klasse
        if "iban" in werte and _text(werte["iban"]):
            p.iban = iban_utils.normalisieren(_text(werte["iban"]))
            if not iban_utils.ist_gueltig(p.iban):
                warnungen.append(f"Zeile {nr}: IBAN von {p.name} ist ungültig ({iban_utils.pruefen(p.iban)[1]})")
        for f in ("geburtsdatum", "beitritt_datum", "austritt_datum"):
            if f in werte and _text(werte[f]):
                iso = de_zu_iso(werte[f])
                if iso:
                    setattr(p, f, iso)
                else:
                    warnungen.append(f"Zeile {nr}: Datum '{_text(werte[f])}' nicht erkannt")
        if "anteile" in werte and _text(werte["anteile"]):
            try:
                p.anteile = max(1, int(float(_text(werte["anteile"]).replace(",", "."))))
            except ValueError:
                pass
        if "mitglieds_nr" in werte and _text(werte["mitglieds_nr"]):
            try:
                p.mitglieds_nr = int(float(_text(werte["mitglieds_nr"])))
            except ValueError:
                pass
        personen.append(p)
    return personen, warnungen


# ---------------------------------------------------------------- Export
KOPF_FILL = PatternFill("solid", fgColor="1F5130")
KOPF_FONT = Font(bold=True, color="FFFFFF")
TITEL_FONT = Font(bold=True, size=14, color="1F5130")
DUENN = Side(style="thin", color="C9D3CC")


ZEBRA_FILL = PatternFill("solid", fgColor="F3F7F4")


def _anzeige_laenge(v) -> int:
    if v is None:
        return 0
    if isinstance(v, (date, datetime)):
        return 10
    if isinstance(v, float):
        return len(f"{v:,.2f}")
    return max(len(teil) for teil in str(v).split("\n"))


def _tabelle(ws, start_zeile: int, kopf: list[str], zeilen: list[list], breiten: list[int] | None = None):
    for i, k in enumerate(kopf, start=1):
        c = ws.cell(row=start_zeile, column=i, value=k)
        c.fill, c.font = KOPF_FILL, KOPF_FONT
        c.alignment = Alignment(vertical="center")
    ws.row_dimensions[start_zeile].height = 22
    for r, z in enumerate(zeilen, start=start_zeile + 1):
        zebra = (r - start_zeile) % 2 == 0
        for i, v in enumerate(z, start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = Border(bottom=DUENN)
            c.alignment = Alignment(vertical="center")
            if zebra:
                c.fill = ZEBRA_FILL
            if isinstance(v, (date, datetime)):
                c.number_format = "DD.MM.YYYY"
                c.alignment = Alignment(horizontal="left", vertical="center")
    for i, k in enumerate(kopf, start=1):
        # Überschrift + Platz für den Filter-Pfeil, Inhalt + etwas Luft
        w_kopf = len(str(k)) * 1.15 + 5
        w_inhalt = max([_anzeige_laenge(z[i - 1]) for z in zeilen if i - 1 < len(z)][:500] or [0]) * 1.1 + 3
        w = max(w_kopf, w_inhalt)
        if breiten and i <= len(breiten):
            w = max(w, breiten[i - 1])
        ws.column_dimensions[get_column_letter(i)].width = min(max(w, 9), 55)
    if zeilen:
        ws.auto_filter.ref = f"A{start_zeile}:{get_column_letter(len(kopf))}{start_zeile + len(zeilen)}"
    ws.freeze_panes = ws.cell(row=start_zeile + 1, column=1)
    # Druck: Querformat, auf Seitenbreite einpassen, Kopfzeile wiederholen
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{start_zeile}:{start_zeile}"
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.oddFooter.center.text = "Seite &P von &N"


def _plz(v):
    v = (v or "").strip()
    return int(v) if v.isdigit() and not v.startswith("0") else (v or None)


def _d(iso):
    if not iso:
        return None
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").date()
    except ValueError:
        return iso


PERSONEN_KOPF = ["Mitglieds-Nr.", "Nachname", "Vorname", "Klasse", "Status", "Beitritt", "Austritt",
                 "Austrittsgrund", "Anteile", "IBAN", "IBAN gültig", "Kontoinhaber", "E-Mail",
                 "Telefon", "Adresse", "PLZ", "Ort", "Geburtsdatum", "Info erwünscht", "Notizen"]


def _personen_zeile(p: Person, iban_voll: bool = True) -> list:
    return [p.mitglieds_nr, p.nachname, p.vorname, p.klasse, p.status, _d(p.beitritt_datum),
            _d(p.austritt_datum), p.austritt_grund or None, p.anteile if p.beitritt_datum else None,
            (iban_utils.formatieren(p.iban) if iban_voll else iban_utils.maskieren(p.iban)) or None,
            ("ja" if p.iban_gueltig else "NEIN") if p.iban else None, p.kontoinhaber or None, p.email or None,
            p.telefon or None, p.adresse or None, _plz(p.plz), p.ort or None, _d(p.geburtsdatum),
            "ja" if p.info_erwuenscht else "nein", p.notizen or None]


def personen_exportieren(pfad: str | Path, personen: list[Person], titel: str, iban_voll: bool = True):
    wb = Workbook()
    ws = wb.active
    ws.title = "Liste"
    ws["A1"] = titel
    ws["A1"].font = TITEL_FONT
    ws["A2"] = f"Erstellt am {date.today().strftime('%d.%m.%Y')} – {len(personen)} Personen"
    _tabelle(ws, 4, PERSONEN_KOPF, [_personen_zeile(p, iban_voll) for p in personen])
    wb.save(pfad)


def ausgetretene_exportieren(pfad: str | Path, personen: list[Person], titel: str, betrag_pro_anteil: float):
    wb = Workbook()
    ws = wb.active
    ws.title = "Ausgetretene"
    ws["A1"] = titel
    ws["A1"].font = TITEL_FONT
    ws["A2"] = f"Erstellt am {date.today().strftime('%d.%m.%Y')} – {len(personen)} Austritte"
    kopf = ["Mitglieds-Nr.", "Nachname", "Vorname", "Klasse", "Beitritt", "Austritt", "Grund",
            "Anteile", "Auszahlung (€)", "IBAN", "IBAN gültig", "Kontoinhaber", "E-Mail"]
    zeilen = [[p.mitglieds_nr, p.nachname, p.vorname, p.klasse, _d(p.beitritt_datum), _d(p.austritt_datum),
               p.austritt_grund, p.anteile, round((p.anteile or 0) * betrag_pro_anteil, 2),
               iban_utils.formatieren(p.iban), ("ja" if p.iban_gueltig else "NEIN") if p.iban else "fehlt",
               p.kontoinhaber or f"{p.vorname} {p.nachname}", p.email] for p in personen]
    _tabelle(ws, 4, kopf, zeilen)
    for r in range(5, 5 + len(zeilen)):
        ws.cell(row=r, column=9).number_format = '#,##0.00 "€"'
    if zeilen:
        r = 5 + len(zeilen)
        ws.cell(row=r, column=7, value="Summe").font = Font(bold=True)
        ws.cell(row=r, column=8, value=f"=SUM(H5:H{r - 1})").font = Font(bold=True)
        c = ws.cell(row=r, column=9, value=f"=SUM(I5:I{r - 1})")
        c.font, c.number_format = Font(bold=True), '#,##0.00 "€"'
    wb.save(pfad)


def revision_exportieren(pfad: str | Path, rev: dict, name_genossenschaft: str, betrag_pro_anteil: float):
    wb = Workbook()
    ws = wb.active
    ws.title = "Übersicht"
    ws["A1"] = f"{name_genossenschaft} – Mitgliederstand für die Revision"
    ws["A1"].font = TITEL_FONT
    ws["A2"] = f"Erstellt am {date.today().strftime('%d.%m.%Y')}"
    daten = [
        ("Stichtag", iso_zu_de(rev["stichtag"])),
        ("Prüfungszeitraum", f"{iso_zu_de(rev['von'])} – {iso_zu_de(rev['bis'])}"),
        ("", ""),
        ("Mitgliederstand zu Beginn des Zeitraums", rev["stand_beginn"]),
        ("+ Beitritte im Zeitraum", len(rev["beitritte"])),
        ("− Austritte im Zeitraum", len(rev["austritte"])),
        ("Mitgliederstand am Stichtag", rev["anzahl_mitglieder"]),
        ("", ""),
        ("Geschäftsanteile gesamt", rev["anteile"]),
        ("Betrag pro Anteil (€)", betrag_pro_anteil),
        ("Geschäftsguthaben gesamt (€)", rev["geschaeftsguthaben"]),
        ("", ""),
        ("Mitglieder ohne IBAN", rev["iban_fehlend"]),
        ("Mitglieder mit ungültiger IBAN", rev["iban_ungueltig"]),
    ]
    for i, (k, v) in enumerate(daten, start=4):
        ws.cell(row=i, column=1, value=k).font = Font(bold=k.startswith("Mitgliederstand am"))
        c = ws.cell(row=i, column=2, value=v)
        if "€" in k:
            c.number_format = '#,##0.00 "€"'
        if k.startswith("Mitgliederstand am"):
            c.font = Font(bold=True)
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 26
    if rev["austrittsgruende"]:
        r = 4 + len(daten) + 1
        ws.cell(row=r, column=1, value="Austrittsgründe im Zeitraum").font = Font(bold=True)
        for j, (g, n) in enumerate(sorted(rev["austrittsgruende"].items(), key=lambda x: -x[1]), start=1):
            ws.cell(row=r + j, column=1, value=g)
            ws.cell(row=r + j, column=2, value=n)

    ws2 = wb.create_sheet("Nach Klasse")
    zeilen = [[k, d["mitglieder"], d["anteile"], d["beitritte"], d["austritte"]] for k, d in rev["pro_klasse"].items()]
    zeilen.append(["Summe", sum(z[1] for z in zeilen), sum(z[2] for z in zeilen),
                   sum(z[3] for z in zeilen), sum(z[4] for z in zeilen)])
    _tabelle(ws2, 1, ["Klasse", "Mitglieder am Stichtag", "Anteile", "Beitritte im Zeitraum",
                      "Austritte im Zeitraum"], zeilen, [18, 22, 10, 22, 22])
    for c in ws2[len(zeilen) + 1]:
        c.font = Font(bold=True)

    ws3 = wb.create_sheet("Nach Jahr")
    zeilen = [[j, d["beitritte"], d["austritte"], d["beitritte"] - d["austritte"], d["stand_ende"]]
              for j, d in rev["pro_jahr"].items()]
    _tabelle(ws3, 1, ["Jahr", "Beitritte", "Austritte", "Saldo", "Stand 31.12."], zeilen, [10, 12, 12, 10, 14])

    ws4 = wb.create_sheet("Mitglieder am Stichtag")
    _tabelle(ws4, 1, ["Mitglieds-Nr.", "Nachname", "Vorname", "Klasse", "Beitritt", "Anteile", "IBAN gültig"],
             [[p.mitglieds_nr, p.nachname, p.vorname, p.klasse, _d(p.beitritt_datum), p.anteile,
               ("ja" if p.iban_gueltig else "NEIN") if p.iban else "fehlt"] for p in rev["mitglieder"]])

    for blatt, schluessel in (("Beitritte", "beitritte"), ("Austritte", "austritte")):
        w = wb.create_sheet(blatt)
        _tabelle(w, 1, ["Datum", "Mitglieds-Nr.", "Nachname", "Vorname", "Klasse", "Bemerkung"],
                 [[_d(e["datum"]), e["mitglieds_nr"], e["nachname"], e["vorname"], e["klasse"],
                   e["beschreibung"]] for e in rev[schluessel]])
    wb.save(pfad)


def vorlage_erstellen(pfad: str | Path):
    """Leere Importvorlage mit den empfohlenen Spalten."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Klassenliste"
    kopf = ["Nachname", "Vorname", "Klasse", "Geburtsdatum", "E-Mail", "IBAN", "Kontoinhaber", "Beitrittsdatum", "Anteile"]
    _tabelle(ws, 1, kopf, [["Muster", "Max", "4IT", date(2008, 5, 1), "max.muster@josephinum.com",
                            "AT61 1904 3002 3457 3201", "", None, 1]],
             [16, 14, 8, 14, 32, 30, 20, 16, 9])
    wb.save(pfad)
