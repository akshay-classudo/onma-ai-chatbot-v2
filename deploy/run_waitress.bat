@echo off
REM Production entrypoint for Windows — Waitress (pure-Python WSGI server,
REM Gunicorn doesn't run on Windows). Put a reverse proxy (IIS/Apache) in
REM front for TLS termination; this only binds plain HTTP on 127.0.0.1.
REM
REM To run as a background Windows Service instead of a console window,
REM wrap this script with NSSM: https://nssm.cc/
REM   nssm install OnmaChatbot "C:\path\to\deploy\run_waitress.bat"
REM   nssm start OnmaChatbot

cd /d "%~dp0.."
venv\Scripts\python.exe manage.py collectstatic --noinput
venv\Scripts\waitress-serve.exe --listen=127.0.0.1:8000 --threads=8 onma_bot.wsgi:application
