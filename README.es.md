# QUANTUM Inspector (QA Snapshot Inspector)

GUI profesional en Python para inspeccionar snapshots Android (volcados UIAutomator + capturas), revisar el estado en vivo del dispositivo y generar localizadores robustos para automatización QA.

Propietario del proyecto y autoridad técnica: David Erik García Arenas (QA, Paradox Cat).

![Interfaz de QUANTUM Inspector - V1 PoC](docs/v1-poc.png)

V1 PoC (build actual).

## Qué hace

- Espejo en vivo por ADB (opcional) para inspeccionar la UI actual en tiempo real.
- Inspección offline de snapshots guardados.
- Navegación del árbol de UI con superposición sobre la captura.
- Panel de inspector con propiedades del nodo (texto, bounds, resource-id, etc.).
- Sugerencias de localizadores (XPath + formatos Appium Java/Python).

## Visuales adicionales

![Interfaz de QUANTUM Inspector - Ejemplo](docs/ui-example.png)

UI_Example: captura guía para explicar qué muestra cada sección al abrir una pantalla.

## Artículo / documentación (borrador)

- [QUANTUM_Article_Final.pdf](docs/QUANTUM_Article_Final.pdf) — documentación/artículo en evolución del PoC. Solo en español por ahora.

## Requisitos

- Python 3.11+
- Windows 11 (diseñado para, pero funciona en macOS/Linux)
- ADB (opcional, para espejo en vivo y captura)

## Formato de snapshot

Cada carpeta de snapshot puede incluir:

- screenshot.png (screencap de ADB)
- dump.uix (volcado XML de UIAutomator)
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