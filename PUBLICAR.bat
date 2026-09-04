@echo off
title Publicar Tablero QA
cd /d "%~dp0"
echo Publicando el tablero para toda la oficina...
echo.
node herramientas\publicar.mjs %*
if errorlevel 1 (
  echo.
  echo Algo fallo. Revisa el mensaje de arriba.
)
echo.
pause
