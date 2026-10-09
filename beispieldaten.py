"""Erzeugt erfundene Beispieldaten zum Testen und Vorführen.

python beispieldaten.py   -> legt zwei Beispiel-Klassenlisten (Excel) im Ordner 'beispiele' an
(Die Demo-Datenbank wird über 'python main.py --demo' automatisch befüllt.)
Alle Namen und IBANs sind frei erfunden.
"""
import random
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook

VORNAMEN = ["Lukas", "Anna", "Jakob", "Lena", "Maximilian", "Sophie", "Felix", "Laura", "Tobias", "Julia",
            "Elias", "Hannah", "David", "Marie", "Simon", "Katharina", "Florian", "Theresa", "Paul", "Lisa",
            "Moritz", "Magdalena", "Matthias", "Johanna", "Stefan", "Viktoria", "Andreas", "Sarah", "Michael", "Eva"]
NACHNAMEN = ["Gruber", "Huber", "Wagner", "Pichler", "Steiner", "Moser", "Mayer", "Hofer", "Leitner", "Berger",
             "Fuchs", "Eder", "Fischer", "Schmid", "Winkler", "Weber", "Schwarz", "Maier", "Schneider", "Reiter",
             "Mayr", "Brunner", "Lang", "Baumgartner", "Auer", "Binder", "Lechner", "Wolf", "Wallner", "Aigner"]
ORTE = [("3250", "Wieselburg"), ("3390", "Melk"), ("3300", "Amstetten"), ("3370", "Ybbs an der Donau"),
        ("3270", "Scheibbs"), ("3263", "Randegg"), ("3251", "Purgstall")]
BANKLEITZAHLEN = ["32000", "20111", "12000", "14000", "32585", "20202"]


def at_iban(rng: random.Random) -> str:
    """Erzeugt eine formal gültige (erfundene) österreichische IBAN."""
    bban = rng.choice(BANKLEITZAHLEN) + "".join(str(rng.randint(0, 9)) for _ in range(11))
    zahl = int("".join(str(int(c, 36)) for c in bban + "AT00"))
    return f"AT{98 - zahl % 97:02d}{bban}"


def _person(rng, klasse, jahrgang):
    vn, nn = rng.choice(VORNAMEN), rng.choice(NACHNAMEN)
    plz, ort = rng.choice(ORTE)
    geb = date(jahrgang, 1, 1) + timedelta(days=rng.randint(0, 364))
    return {
        "vorname": vn, "nachname": nn, "klasse": klasse, "geburtsdatum": geb,
        "email": f"{vn.lower()}.{nn.lower()}@josephinum.com".replace("ä", "ae").replace("ö", "oe").replace("ü", "ue"),
        "plz": plz, "ort": ort, "adresse": f"{rng.choice(['Hauptstraße', 'Bahnstraße', 'Feldweg', 'Kirchenplatz'])} {rng.randint(1, 60)}",
        "iban": at_iban(rng),
    }


def klasse_erzeugen(rng, klasse, jahrgang, anzahl):
    gesehen, out = set(), []
    while len(out) < anzahl:
        p = _person(rng, klasse, jahrgang)
        if (p["vorname"], p["nachname"]) in gesehen:
            continue
        gesehen.add((p["vorname"], p["nachname"]))
        out.append(p)
    return out


def demo_fuellen(db):
    """Füllt eine (leere) Datenbank mit einer realistischen Historie."""
    from care.database import AUSTRITTSGRUENDE, Person
    rng = random.Random(42)
    klassen = [("1IT", 2010), ("2IT", 2009), ("3IT", 2008), ("4IT", 2008), ("5IT", 2007),
               ("1LW", 2010), ("3LW", 2008), ("LWB 25", 2006)]
    heute = date.today()
    for klasse, jg in klassen:
        for d in klasse_erzeugen(rng, klasse, jg, rng.randint(14, 22)):
            p = Person(**{k: v for k, v in d.items() if k != "geburtsdatum"}, geburtsdatum=d["geburtsdatum"].isoformat())
            if rng.random() < 0.12:
                p.iban = ""
            elif rng.random() < 0.04:
                p.iban = p.iban[:-1] + str((int(p.iban[-1]) + 1) % 10)   # absichtlicher Tippfehler
            p.info_erwuenscht = 0 if rng.random() < 0.1 else 1
            if rng.random() < 0.07:
                p.email = ""
            db.person_speichern(p, protokoll="Demo-Daten")
            if rng.random() < 0.72:
                schuljahre = max(0, int(klasse[0]) - 1) if klasse[0].isdigit() else 2
                start = date(heute.year - schuljahre - (0 if heute.month >= 9 else 1), 9, 1)
                beitritt = start + timedelta(days=rng.randint(0, 120))
                if beitritt > heute:
                    beitritt = heute - timedelta(days=rng.randint(1, 30))
                db.beitritt_erfassen(p.id, beitritt.isoformat(), rng.choice([1, 1, 1, 2, 3]))
                if rng.random() < 0.16:
                    austritt = beitritt + timedelta(days=rng.randint(60, 500))
                    if austritt > heute + timedelta(days=120):
                        austritt = heute + timedelta(days=rng.randint(10, 90))
                    db.austritt_erfassen(p.id, austritt.isoformat(), rng.choice(AUSTRITTSGRUENDE[:3]))


def beispiel_excel(ordner: Path):
    ordner.mkdir(exist_ok=True)
    rng = random.Random(7)
    # Variante 1: übliche Klassenliste mit getrennten Spalten und Titelzeilen
    wb = Workbook()
    ws = wb.active
    ws.title = "4IT"
    ws.append(["HBLFA Francisco Josephinum – Klassenliste 4IT"])
    ws.append(["Schuljahr 2026/27"])
    ws.append([])
    ws.append(["Nr.", "Familienname", "Vorname", "Geb.Datum", "E-Mail", "IBAN"])
    for i, p in enumerate(klasse_erzeugen(rng, "4IT", 2008, 18), start=1):
        iban = p["iban"] if rng.random() < 0.8 else ""
        ws.append([i, p["nachname"], p["vorname"], p["geburtsdatum"], p["email"],
                   " ".join(iban[j:j + 4] for j in range(0, len(iban), 4))])
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["E"].width = 34
    ws.column_dimensions["F"].width = 28
    wb.save(ordner / "Beispiel_Klassenliste_4IT.xlsx")

    # Variante 2: ein Namensfeld "Nachname Vorname" und Klassenspalte
    wb = Workbook()
    ws = wb.active
    ws.title = "Schüler"
    ws.append(["Schüler/in", "Klasse", "Geburtsdatum", "Wohnort"])
    for p in klasse_erzeugen(rng, "LWB 25", 2006, 15):
        ws.append([f"{p['nachname']} {p['vorname']}", "LWB 25", p["geburtsdatum"].strftime("%d.%m.%Y"), p["ort"]])
    ws.column_dimensions["A"].width = 24
    wb.save(ordner / "Beispiel_Klassenliste_LWB25.xlsx")


if __name__ == "__main__":
    ziel = Path(__file__).resolve().parent / "beispiele"
    beispiel_excel(ziel)
    print(f"Beispiel-Klassenlisten erstellt in {ziel}")
