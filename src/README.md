# QA Snapshot Inspector & Locator Assistant

A Python desktop GUI for QA engineers to inspect Android UI snapshots offline, debug locator issues, and generate robust/scoped Page Object locators.

## Prerequisites

*   Python 3.11+
*   Windows 11 (Developed for, but works on Mac/Linux)
*   ADB (optional, for online capture)

## Installation

1) Create a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

2) Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Run the tool
```bash
python src/qa_snapshot_tool/main.py