@echo off
title Tablero QA - Servidor (SQLite)
cd /d "%~dp0"
echo Iniciando el Tablero QA con base de datos SQLite...
python servidor.py
if errorlevel 1 py servidor.py
pause
