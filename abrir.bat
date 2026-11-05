@echo off
title Tradutor SQL BigQuery
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale em https://www.python.org/downloads/ e tente de novo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Preparando o app pela primeira vez. Isso pode levar alguns minutos...
  python -m venv .venv
)

".venv\Scripts\python.exe" -c "import streamlit, anthropic, sqlglot, dotenv" >nul 2>nul
if errorlevel 1 (
  echo Instalando o que falta. Isso pode levar alguns minutos...
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
  if errorlevel 1 (
    echo Nao consegui instalar. Confira sua internet e tente de novo.
    pause
    exit /b 1
  )
)

start "" /b cmd /c "ping -n 5 127.0.0.1 >nul & start "" http://localhost:8501"
echo O app esta aberto no navegador. Feche esta janela para encerrar.
".venv\Scripts\python.exe" -m streamlit run app.py
