# C.A.R.E – Mitgliederverwaltung der FJ Genossenschaft

Schulprojekt BW · HBLFA Francisco Josephinum Wieselburg

Desktop-Programm (Python, PyQt5, SQLite) zur Verwaltung der Mitglieder: An- und Abmeldungen,
Import der Klassenlisten aus Excel, IBAN-Prüfung, Liste der Ausgetretenen und Auswertungen
für die Prüfung durch den Revisionsverband.

## Starten

1. Python 3 installieren (python.org, beim Installieren **„Add python.exe to PATH“** anhaken).
2. Doppelklick auf **`Starten.bat`**. Beim ersten Start werden PyQt5 und openpyxl automatisch installiert.
3. Zum Ausprobieren gibt es **`Demo starten.bat`**. Das öffnet eine eigene Demo-Datenbank mit rund 150
   erfundenen Personen, die echten Daten bleiben davon unberührt.

Alternativ: `pip install -r requirements.txt`, danach `python main.py` (bzw. `python main.py --demo`).

Die Daten liegen in `daten/care.db`. Eine Sicherung legst du über **Mehr → Datenbank sichern** an.

## Typischer Ablauf

| Schritt | Wo im Programm |
|---|---|
| Klassenliste aus Excel übernehmen | **Excel importieren …** → Spalten prüfen → „Nur als Klassenliste übernehmen“ |
| Beitrittserklärungen eintragen | Personen in der Liste anklicken (Strg/Umschalt für mehrere) → **Beitritt erfassen** |
| Austrittserklärung eintragen | Mitglied(er) auswählen → **Austritt erfassen** (Datum + Grund) |
| Details einer Person | Person anklicken: rechts erscheinen Mitgliedschaft, IBAN, Kontakt und der Verlauf |
| Liste der Ausgetretenen | Seite **Ausgetretene** → **Liste als Excel speichern** (mit Auszahlungsbetrag und IBAN) |
| Revisionsprüfung | Seite **Revision / Statistik** → Zeitraum und Stichtag wählen → **Revisionsbericht als Excel** |
| Mitglieder informieren | Seite **Mitgliederinfo** → Adressen kopieren (ins BCC-Feld) → **Versand protokollieren** |

## Funktionen

- **Excel-Import** (.xlsx, .xls, .csv): Die Überschriftenzeile und die Spalten (Vorname, Nachname,
  „Name komplett“, Klasse, Geburtsdatum, E-Mail, IBAN, Beitrittsdatum …) werden automatisch erkannt
  und lassen sich per Auswahlliste ändern. Steht die Klasse nicht in der Liste, wird sie aus dem
  Dateinamen übernommen (z. B. `Klassenliste_4IT.xlsx` → 4IT) oder kann eingetippt werden.
  Doppelte Personen werden erkannt und nur ergänzt. Eine leere Vorlage gibt es unter
  **Mehr → Importvorlage speichern**.
- **Status** jeder Person: *Kein Mitglied*, *Mitglied*, *Austritt angemeldet* (Austrittsdatum liegt in der
  Zukunft), *Ausgetreten*. Auch ein Wiedereintritt ist möglich.
- **Mitglieds-Nummern** werden fortlaufend vergeben, **Geschäftsanteile** pro Mitglied erfasst
  (Betrag pro Anteil unter **Mehr → Einstellungen**).
- **Sortieren und Filtern**: Klick auf eine Spaltenüberschrift sortiert die Liste. Gefiltert wird nach
  Status, Klasse und IBAN (fehlt/ungültig/gültig), dazu gibt es eine Volltextsuche.
- **IBAN-System**: Prüfung mit Prüfziffer (Modulo 97), maskierte Anzeige (`AT61 •••• •••• •••• 3201`),
  vollständige Anzeige über **Mehr → IBANs vollständig anzeigen** (unten in der Seitenleiste), Kopieren mit einem Klick.
- **Verlauf** pro Person: Beitritt, Austritt, Änderungen, versendete Infos und Notizen mit Datum.
- **Revision**: Mitgliederstand am Stichtag, Stand zu Beginn, Beitritte und Austritte im Zeitraum,
  Anteile und Geschäftsguthaben, dazu Auswertungen nach Klasse (z. B. LWB 25), nach Jahr und nach
  Austrittsgrund. Der Excel-Bericht enthält die Blätter Übersicht, Nach Klasse, Nach Jahr,
  Mitglieder am Stichtag, Beitritte und Austritte.
- **Export** jeder gefilterten Ansicht nach Excel (Strg+S).

## Aufbau des Codes

```
main.py              Programmstart
beispieldaten.py     erfundene Demo-Daten und Beispiel-Klassenlisten
care/database.py     SQLite-Datenbank: Tabellen, Beitritt/Austritt, Auswertungen
care/excel_io.py     Excel-Import (Spaltenerkennung) und Excel-Export
care/iban_utils.py   IBAN prüfen, formatieren, maskieren
care/dialogs.py      Dialoge: Person, Beitritt, Austritt, Import, Einstellungen
care/ui_elemente.py  Design: Farben, Stylesheet, Karten, Kacheln, Status-Etiketten, Diagramme
care/main_window.py  Hauptfenster mit Seitenleiste und vier Seiten
beispiele/           zwei Beispiel-Klassenlisten zum Testen des Imports
```

### Datenbank

- `personen`: Stammdaten, Bankverbindung und aktueller Stand der Mitgliedschaft
- `ereignisse`: Verlauf (Beitritt, Austritt, Änderung, Info, Notiz). Die Zahlen für die Revision
  werden aus dieser Tabelle berechnet, damit auch Wiedereintritte richtig gezählt werden.
- `einstellungen`: Name der Genossenschaft, Betrag pro Anteil

## Datenschutz

Die Datenbank enthält personenbezogene Daten und IBANs. Sie liegt nur lokal auf dem PC, deshalb
gehört `daten/care.db` nicht in Cloud-Ordner oder E-Mails. Gesichert wird über **Datenbank sichern**
auf einem geschützten Speicherort.
