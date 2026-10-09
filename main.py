"""C.A.R.E – Mitgliederverwaltung der FJ Genossenschaft.

Start:  python main.py          (eigene Daten in daten/care.db)
        python main.py --demo   (Demo-Datenbank mit Beispieldaten, daten/care_demo.db)
"""
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QMessageBox

from care.database import Datenbank
from care.main_window import Hauptfenster, stil_erzeugen

BASIS = Path(__file__).resolve().parent


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("C.A.R.E")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(stil_erzeugen())

    demo = "--demo" in sys.argv
    pfad = BASIS / "daten" / ("care_demo.db" if demo else "care.db")
    try:
        db = Datenbank(pfad)
        if demo and not db.alle_personen():
            from beispieldaten import demo_fuellen
            demo_fuellen(db)
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(None, "C.A.R.E", f"Die Datenbank konnte nicht geöffnet werden:\n{e}")
        return 1
    fenster = Hauptfenster(db)
    if demo:
        fenster.setWindowTitle(fenster.windowTitle() + "  [DEMO-DATEN]")
    fenster.show()
    code = app.exec_()
    db.schliessen()
    return code


if __name__ == "__main__":
    sys.exit(main())
