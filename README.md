# PY-MACRO
Automated Macro Wire
# pymac — Automated Macro Wire (FINAL REVISED)

**pymac.py** is a lightweight, resilient macro monitoring engine (news → sentiment → impact → market snapshot) combining news feeds, Truth Social scraping, quick stock/crypto metrics, and a persistent SQLite store.

This release is the **FINAL REVISED** edition (2025) focused on stability (no hangs), pragmatic data sources, and conservative enrichment for automated macro signal workflows.

---

## Features
- Ingests RSS news from major outlets (NYT, Reuters, CNBC, Yahoo Finance)  
- Scrapes latest posts from Truth Social (public page scraping; no API key) and flags fiscal posts as **ULTRA-HIGH** priority  
- Lightweight sentiment via `textblob` and macro keyword scoring  
- Quick stock and crypto metrics via `yfinance` and CoinGecko (no paid API required)  
- Persistent storage in `macro_wire.db` (SQLite) for news, quarantine events, impact records, and market metrics  
- Quarantine logic for macro-level items (e.g., Fed/CPI/Trump-fiscal) to highlight items requiring manual review  
- Robust error handling and logging to `pymac.log`  
- Designed to run as a cron / systemd service or manually in a virtualenv

---

## Quick Start (recommended)

1. Create & activate a Python virtualenv

**Windows (PowerShell)**:
```powershell
python -m venv myenv
.\myenv\Scripts\Activate.ps1
