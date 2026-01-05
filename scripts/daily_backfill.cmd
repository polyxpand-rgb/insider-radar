@echo off
cd /d C:\dev\insider-radar\apps\worker
C:\dev\insider-radar\.venv\Scripts\python.exe -m worker.cli backfill --days 3 --max-filings-per-day 200 >> C:\dev\insider-radar\logs\worker-daily.log 2>&1
