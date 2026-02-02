# QUANTUM Inspector (QA Snapshot Inspector)

<p align="center">
	<img src="assets/icons/quantum.svg" width="140" alt="QUANTUM Icon" />
</p>

<p align="center">
	<b>Professioneller Android-Snapshot-Inspector</b><br/>
	Live-Mirror + Offline-Analyse + robuste Locator
</p>

<p align="center">
	<a href="README.de.md"><img src="https://img.shields.io/badge/status-aktiv-2ea043.svg" alt="Status" /></a>
	<a href="README.de.md"><img src="https://img.shields.io/badge/python-3.11%2B-3776AB.svg" alt="Python" /></a>
	<a href="README.de.md"><img src="https://img.shields.io/badge/plattform-windows%2011-0078D4.svg" alt="Plattform" /></a>
	<a href="LICENSE"><img src="https://img.shields.io/badge/lizenz-MIT-8A2BE2.svg" alt="Lizenz" /></a>
</p>

<p align="center">
	<a href="docs/ARCHITECTURE.md">Architektur</a> •
	<a href="docs/USAGE_GUIDE.md">Nutzungsanleitung</a> •
	<a href="docs/TROUBLESHOOTING.md">Fehlerbehebung</a> •
	<a href="docs/QUANTUM%20INSPECTOR%20-%20EN.pdf">Internes Dokument</a>
</p>

Professionelle Python-Desktop-GUI zum Inspizieren von Android-Snapshots (UIAutomator-Dumps + Screenshots), zur Live-Ansicht des Geräts und zur Generierung robuster Locator für QA-Automation.

Projektinhaber und technische Autorität: David Erik García Arenas (QA, Paradox Cat).

![QUANTUM Inspector UI - V1 PoC](docs/v1-poc.png)

V1 PoC (aktueller Build).

> [!NOTE]
> BMW Type Next ist eine lizenzierte Schrift. Wenn sie nicht verfügbar ist, nutzt die UI Segoe UI.

## Was es macht

- Live-Mirror via ADB (optional) zur Echtzeit-Inspektion der UI.
- Stream-Auflösungs-Presets (Native, 4K, 2K, 1080p, 720p, 1024).
- Offline-Inspektion mit dump.uix-Picker + Offline-Logcat-Ansicht.
- UI-Baum mit Auto-Follow bei Hover, Expand bei Fokus und Auswahl-Lock (Enter/Click).
- Inspector-Panel mit Node-Properties (Text, Bounds, Resource-ID, etc.).
- Locator-Vorschläge (XPath + Appium Java/Python Formate).
- Logcat-Tab + separates System-Log-Dock (nicht im Inspector-Tab).
- Re-Capture des letzten Snapshots (schnelles Refresh der aktuellen Quelle).
- Device-IP-Connect + Verlauf zuletzt verwendeter Geräte.
- Device-Profile geladen aus devices.json.
- Performance-Mode (gedrosselte Tree-Updates im Live-Modus).
- Erkennung korrupter Snapshots (Null-Nodes/ungültige Bounds im System Log).

> [!TIP]
> Nutze den Offline-Modus, um Snapshots ohne verbundenes Gerät zu prüfen.

## Zusätzliche Visuals

![QUANTUM Inspector UI - Beispiel](docs/ui-example.png)

UI_Example: Hinweis-Screenshot zur Erklärung der Bereiche beim Öffnen eines Screens.

## Interne Dokumente

| Titel | Link |
| --- | --- |
| QUANTUM INSPECTOR - EN | [docs/QUANTUM%20INSPECTOR%20-%20EN.pdf](docs/QUANTUM%20INSPECTOR%20-%20EN.pdf) |
| Especificaciones Técnicas QUANTUM Inspector Android Automotive | [docs/Especificaciones%20T%C3%A9cnicas%20QUANTUM%20Inspector%20Android%20Automotive.pdf](docs/Especificaciones%20T%C3%A9cnicas%20QUANTUM%20Inspector%20Android%20Automotive.pdf) |
| Whitepaper técnico interno  QUANTUM INSPECTOR 2 | [docs/Whitepaper%20t%C3%A9cnico%20interno%20%20QUANTUM%20INSPECTOR%202.pdf](docs/Whitepaper%20t%C3%A9cnico%20interno%20%20QUANTUM%20INSPECTOR%202.pdf) |

> [!CAUTION]
> Interne Dokumente sind vertraulich. Nicht außerhalb freigegebener Teams verbreiten.

## Voraussetzungen

- Python 3.11+
- Windows 11 (dafür ausgelegt, funktioniert aber auch auf macOS/Linux)
- ADB (optional, für Live-Mirror und Capture)

## Snapshot-Format

Jeder Snapshot-Ordner kann enthalten:

- screenshot.png (ADB-Screencap)
- dump.uix (UIAutomator XML-Dump)
- focus.txt (optional, Fokusfenster-Übersicht)
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

<img src="docs/bernard-tennis.gif" width="120" alt="Bernard Tennis (Easter Egg)" />