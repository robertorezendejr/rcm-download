@echo off
chcp 65001 >nul
echo ========================================================
echo  Automacao MIO - Download RCM, Relatorios (2, 5, 10) e PCS
echo ========================================================
echo.
if not exist .venv\Scripts\python.exe (
    echo [ERRO] Ambiente virtual nao encontrado.
    echo Execute primeiro o instalador: instalar_windows.bat
    echo.
    pause
    exit /b 1
)
.venv\Scripts\python.exe main.py
echo.
pause
