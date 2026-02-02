# QUANTUM Inspector (QA Snapshot Inspector)

<p align="center">
	<img src="assets/icons/quantum.svg" width="140" alt="QUANTUM Icon" />
</p>

<p align="center">
	<b>Inspector profesional de snapshots Android</b><br/>
	Espejo en vivo + análisis offline + localizadores robustos
</p>

<p align="center">
	<a href="README.es.md"><img src="https://img.shields.io/badge/estado-activo-2ea043.svg" alt="Estado" /></a>
	<a href="README.es.md"><img src="https://img.shields.io/badge/python-3.11%2B-3776AB.svg" alt="Python" /></a>
	<a href="README.es.md"><img src="https://img.shields.io/badge/plataforma-windows%2011-0078D4.svg" alt="Plataforma" /></a>
	<a href="LICENSE"><img src="https://img.shields.io/badge/licencia-MIT-8A2BE2.svg" alt="Licencia" /></a>
</p>

<p align="center">
	<a href="docs/ARCHITECTURE.md">Arquitectura</a> •
	<a href="docs/USAGE_GUIDE.md">Guía de uso</a> •
	<a href="docs/TROUBLESHOOTING.md">Solución de problemas</a> •
	<a href="docs/QUANTUM%20INSPECTOR%20-%20EN.pdf">Documento interno</a>
</p>

GUI profesional en Python para inspeccionar snapshots Android (volcados UIAutomator + capturas), revisar el estado en vivo del dispositivo y generar localizadores robustos para automatización QA.

Propietario del proyecto y autoridad técnica: David Erik García Arenas (QA, Paradox Cat).

![Interfaz de QUANTUM Inspector - V1 PoC](docs/v1-poc.png)

V1 PoC (build actual).

> [!NOTE]
> BMW Type Next es una fuente con licencia. Si no está disponible, la UI usa Segoe UI.

## Qué hace

- Espejo en vivo por ADB (opcional) para inspeccionar la UI actual en tiempo real.
- Presets de resolución del stream (Nativa, 4K, 2K, 1080p, 720p, 1024).
- Inspección offline con selector de dump.uix + vista de logcat offline.
- Árbol de UI con auto-follow en hover, expand en foco y bloqueo de selección (Enter/click).
- Panel de inspector con propiedades del nodo (texto, bounds, resource-id, etc.).
- Sugerencias de localizadores (XPath + formatos Appium Java/Python).
- Pestaña Logcat + dock separado de System Log (no dentro del Inspector).
- Re-captura del último snapshot (refresh rápido de la fuente actual).
- Conexión por IP + historial de dispositivos recientes.
- Perfiles de dispositivos cargados desde devices.json.
- Modo rendimiento (throttling del árbol en vivo).
- Detección de snapshots corruptos (nodos cero/bounds inválidos en System Log).

> [!TIP]
> Usa el modo offline para inspeccionar snapshots sin un dispositivo conectado.

## Visuales adicionales

![Interfaz de QUANTUM Inspector - Ejemplo](docs/ui-example.png)

UI_Example: captura guía para explicar qué muestra cada sección al abrir una pantalla.

## Documentos internos

| Título | Enlace |
| --- | --- |
| QUANTUM INSPECTOR - EN | [docs/QUANTUM%20INSPECTOR%20-%20EN.pdf](docs/QUANTUM%20INSPECTOR%20-%20EN.pdf) |
| Especificaciones Técnicas QUANTUM Inspector Android Automotive | [docs/Especificaciones%20T%C3%A9cnicas%20QUANTUM%20Inspector%20Android%20Automotive.pdf](docs/Especificaciones%20T%C3%A9cnicas%20QUANTUM%20Inspector%20Android%20Automotive.pdf) |
| Whitepaper técnico interno  QUANTUM INSPECTOR 2 | [docs/Whitepaper%20t%C3%A9cnico%20interno%20%20QUANTUM%20INSPECTOR%202.pdf](docs/Whitepaper%20t%C3%A9cnico%20interno%20%20QUANTUM%20INSPECTOR%202.pdf) |

> [!CAUTION]
> Los documentos internos son confidenciales. No distribuir fuera de equipos autorizados.

## Requisitos

- Python 3.11+
- Windows 11 (diseñado para, pero funciona en macOS/Linux)
- ADB (opcional, para espejo en vivo y captura)

## Formato de snapshot

Cada carpeta de snapshot puede incluir:

- screenshot.png (screencap de ADB)
- dump.uix (volcado XML de UIAutomator)
- focus.txt (opcional, resumen de ventana en foco)
- meta.json (info del dispositivo, actividad en foco, timestamps)
- logcat.txt (opcional)

Los archivos faltantes se manejan con advertencias.

## Instalación

1) Crear entorno virtual:

```bash
python -m venv venv
venv\Scripts\activate
```

2) Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Uso

```bash
python src/qa_snapshot_tool/main.py
```

## Notas

- Modo offline: abre cualquier carpeta de snapshot con dump y captura.
- Modo online (opcional): conecta un dispositivo y captura snapshots por ADB.

## Flujo de trabajo (GitFlow)

Este repo sigue GitFlow:

- main: releases estables
- develop: integración activa
- feature/*: nuevas funcionalidades
- hotfix/*: fixes urgentes en main
- release/*: estabilización previa al release

## Archivos del proyecto

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)
- [FAQ.md](FAQ.md)
- [CHANGELOG.md](CHANGELOG.md)
- [LICENSE](LICENSE)

<img src="docs/bernard-tennis.gif" width="120" alt="Bernard tenis (easter egg)" />