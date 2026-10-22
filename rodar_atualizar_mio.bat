@echo off
chcp 65001 >nul
echo ============================================
echo  Atualizar MIO (Baixa RCM, 2, 5, 10 e PCS)
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente nao instalado.
    echo Execute primeiro o arquivo: instalar_windows.bat
    echo.
    pause
    exit /b 1
)

:: Roda o script que baixa tudo
.venv\Scripts\python atualizar_mio.py

echo.
pause
