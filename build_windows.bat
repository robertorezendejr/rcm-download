@echo off
chcp 65001 >nul
echo ============================================
echo  BUILD - Gerando RCM-Download.exe
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente nao instalado.
    echo Execute primeiro o arquivo: instalar_windows.bat
    echo.
    pause
    exit /b 1
)

echo [1/3] Instalando PyInstaller...
.venv\Scripts\pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERRO] Falha ao instalar PyInstaller.
    pause
    exit /b 1
)

echo [2/3] Gerando o executavel (pode demorar alguns minutos)...
.venv\Scripts\pyinstaller --onedir --name RCM-Download --collect-all playwright --hidden-import playwright --noconfirm main.py
if errorlevel 1 (
    echo [ERRO] Falha ao gerar o executavel.
    pause
    exit /b 1
)

echo [3/3] Copiando arquivos de configuracao...
copy /Y config.json dist\RCM-Download\config.json >nul
copy /Y .env.example dist\RCM-Download\.env.example >nul

echo.
echo ============================================
echo  Pronto! Pasta gerada em: dist\RCM-Download\
echo ============================================
echo.
echo Para distribuir:
echo  1. Va ate dist\RCM-Download\
echo  2. Copie .env.example para .env
echo  3. Preencha EMAIL e PASSWORD no .env
echo  4. Clique duas vezes em RCM-Download.exe
echo.
pause
