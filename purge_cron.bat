@echo off
cd /d "%~dp0"
venv\Scripts\python.exe manage.py purge_old_data
