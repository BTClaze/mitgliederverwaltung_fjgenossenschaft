"""IBAN-Hilfsfunktionen: Prüfung (ISO 13616, Modulo 97), Formatierung, Maskierung."""

# Länge der IBAN je Land (Auswahl, deckt die üblichen Fälle ab)
IBAN_LAENGEN = {
    "AT": 20, "DE": 22, "CH": 21, "LI": 21, "IT": 27, "SI": 19, "HR": 21,
    "CZ": 24, "SK": 24, "HU": 28, "PL": 28, "NL": 18, "BE": 16, "LU": 20,
    "FR": 27, "ES": 24, "GB": 22, "IE": 22, "DK": 18, "SE": 24, "FI": 18,
}


def normalisieren(iban: str) -> str:
    """Entfernt Leerzeichen/Bindestriche und macht Großbuchstaben."""
    if not iban:
        return ""
    return "".join(ch for ch in str(iban) if ch.isalnum()).upper()


def pruefen(iban: str) -> tuple[bool, str]:
    """Prüft eine IBAN. Gibt (gültig, Meldung) zurück."""
    iban = normalisieren(iban)
    if not iban:
        return False, "Keine IBAN angegeben"
    if len(iban) < 15 or len(iban) > 34:
        return False, "Ungültige Länge"
    land = iban[:2]
    if not land.isalpha() or not iban[2:4].isdigit():
        return False, "Muss mit Ländercode und zwei Prüfziffern beginnen (z. B. AT61…)"
    soll = IBAN_LAENGEN.get(land)
    if soll and len(iban) != soll:
        return False, f"{land}-IBANs haben {soll} Stellen (hier {len(iban)})"
    umgestellt = iban[4:] + iban[:4]
    ziffern = "".join(str(int(ch, 36)) for ch in umgestellt)
    if int(ziffern) % 97 != 1:
        return False, "Prüfziffer falsch – Tippfehler?"
    return True, "IBAN gültig"


def ist_gueltig(iban: str) -> bool:
    return pruefen(iban)[0]


def formatieren(iban: str) -> str:
    """AT611904300234573201 -> AT61 1904 3002 3457 3201"""
    iban = normalisieren(iban)
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))


def maskieren(iban: str) -> str:
    """Zeigt nur Ländercode/Prüfziffer und die letzten 4 Stellen."""
    iban = normalisieren(iban)
    if not iban:
        return ""
    if len(iban) <= 8:
        return formatieren(iban)
    roh = iban[:4] + "•" * (len(iban) - 8) + iban[-4:]
    return " ".join(roh[i:i + 4] for i in range(0, len(roh), 4))
