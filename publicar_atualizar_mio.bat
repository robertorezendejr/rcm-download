@echo off
setlocal
chcp 65001 >nul

REM Publica sempre a versao distribuivel na raiz da pasta de atualizacao.
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "foreach ($folder in (Get-ChildItem -LiteralPath (Join-Path $env:USERPROFILE 'Downloads') -Directory)) { if ($folder.Name -like '00-Atualiza*') { [Console]::Write($folder.FullName); break } }"`) do set "DESTINO=%%D"
set "BROWSERS=%CD%\playwright-browsers"

if not defined DESTINO (
    echo [ERRO] Pasta de entrega 00-Atualizacao de sistema nao encontrada em Downloads.
    exit /b 1
)

if /I "%~1"=="--verificar-destino" (
    echo Pasta de entrega: %DESTINO%
    exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado.
    exit /b 1
)

if not exist "%BROWSERS%\chromium-1148\chrome-win\chrome.exe" (
    echo [1/3] Baixando o Chromium necessario para o executavel...
    set "PLAYWRIGHT_BROWSERS_PATH=%BROWSERS%"
    .venv\Scripts\python.exe -m playwright install chromium
    if errorlevel 1 exit /b 1
)

echo [2/3] Gerando Atualizar_MIO.exe...
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm --onefile --noconsole --name Atualizar_MIO --collect-all playwright --add-data "playwright-browsers;ms-playwright" atualizar_mio.py
if errorlevel 1 exit /b 1

if not exist "%DESTINO%" mkdir "%DESTINO%"
copy /Y "dist\Atualizar_MIO.exe" "%DESTINO%\Atualizar_MIO.exe" >nul
if errorlevel 1 exit /b 1

echo [3/3] Publicado em: %DESTINO%\Atualizar_MIO.exe
endlocal
