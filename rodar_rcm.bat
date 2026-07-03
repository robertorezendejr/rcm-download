@echo off
chcp 65001 >nul
echo ============================================
echo  Automação RCM - Iniciando...
echo ============================================
echo.

:: Verifica se o ambiente virtual existe
if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente não instalado.
    echo Execute primeiro o arquivo: instalar_windows.bat
    echo.
    pause
    exit /b 1
)

:: Roda o script principal
.venv\Scripts\python main.py

echo.
if errorlevel 1 (
    echo [ERRO] Algo deu errado. Veja os logs em: logs\log.txt
) else (
    echo Arquivo salvo na pasta Downloads do Windows.
)
echo.
pause
