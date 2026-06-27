@echo off
chcp 65001 >nul
echo ============================================
echo  INSTALAÇÃO - Automação RCM
echo ============================================
echo.

:: Verifica se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python não encontrado.
    echo Baixe e instale em: https://www.python.org/downloads/
    echo Marque a opção "Add Python to PATH" durante a instalação.
    pause
    exit /b 1
)

echo [1/2] Criando ambiente virtual...
python -m venv .venv
if errorlevel 1 (
    echo [ERRO] Falha ao criar ambiente virtual.
    pause
    exit /b 1
)

echo [2/2] Instalando dependências...
.venv\Scripts\pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependências.
    pause
    exit /b 1
)

echo Instalação concluída!
echo.
echo ============================================
echo  Tudo pronto! Agora use o arquivo:
echo  rodar_rcm.bat  (duplo clique para baixar)
echo ============================================
echo.
pause
