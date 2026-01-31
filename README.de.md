# QUANTUM Inspector (QA Snapshot Inspector)

Professionelle Python-Desktop-GUI zum Inspizieren von Android-Snapshots (UIAutomator-Dumps + Screenshots), zur Live-Ansicht des Geräts und zur Generierung robuster Locator für QA-Automation.

Projektinhaber und technische Autorität: David Erik García Arenas (QA, Paradox Cat).

![QUANTUM Inspector UI - V1 PoC](docs/v1-poc.png)

## Was es macht

- Live-Mirror via ADB (optional) zur Echtzeit-Inspektion der UI.
- Offline-Inspektion gespeicherter Snapshots.
- UI-Baum-Navigation mit Overlay auf dem Screenshot.
- Inspector-Panel mit Node-Properties (Text, Bounds, Resource-ID, etc.).
- Locator-Vorschläge (XPath + Appium Java/Python Formate).

## Zusätzliche Visuals

![QUANTUM Inspector UI - Beispiel](docs/ui-example.png)

<img src="docs/bernard-tennis.gif" width="120" alt="Bernard Tennis (Easter Egg)" />

![Bernard Tennis (spaß)](docs/bernard-tennis.gif)

## Artikel / Dokumentation (Entwurf)

- [QUANTUM_Article_Final.pdf](docs/QUANTUM_Article_Final.pdf) — fortlaufende Dokumentation/Artikel zum PoC. Derzeit nur auf Spanisch.

## Voraussetzungen

- Python 3.11+
- Windows 11 (dafür ausgelegt, funktioniert aber auch auf macOS/Linux)
- ADB (optional, für Live-Mirror und Capture)

## Snapshot-Format

Jeder Snapshot-Ordner kann enthalten:

- screenshot.png (ADB-Screencap)
- dump.uix (UIAutomator XML-Dump)
- meta.json (Geräteinfos, fokussierte Activity, Zeitstempel)
- logcat.txt (optional)

Fehlende Dateien werden mit Warnungen behandelt.

## Installation

1) Virtuelle Umgebung erstellen:

```bash
python -m venv venv
venv\Scripts\activate
```

2) Abhängigkeiten installieren:

```bash
pip install -r requirements.txt
```

## Nutzung

```bash
python src/qa_snapshot_tool/main.py
```

## Hinweise

- Offline-Modus: Öffne einen Snapshot-Ordner mit Dump und Screenshot.
- Online-Modus (optional): Gerät verbinden und Snapshots via ADB aufnehmen.

## Workflow (GitFlow)

Dieses Repo folgt GitFlow:

- main: stabile Releases
- develop: aktive Integration
- feature/*: neue Features
- hotfix/*: dringende Fixes auf main
- release/*: Release-Stabilisierung

## Projektdateien

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)
- [FAQ.md](FAQ.md)
- [CHANGELOG.md](CHANGELOG.md)
- [LICENSE](LICENSE)

## Screenshot

Lege das Bild unter docs/screenshot.png ab, damit es im README angezeigt wird.
