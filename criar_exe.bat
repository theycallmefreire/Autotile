@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Criando AutoTile.exe

echo [1/3] Verificando Python...
python -c "import sys" >nul 2>nul
if %errorlevel% neq 0 (
    echo Python nao encontrado. Instalando via winget...
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    echo.
    echo Feche esta janela e abra o criar_exe.bat de novo.
    pause
    exit /b 0
)

echo [2/3] Instalando dependencias...
python -m pip install --upgrade pip --quiet
python -m pip install --upgrade -r requirements.txt pyinstaller --quiet
if %errorlevel% neq 0 (
    echo Erro ao instalar dependencias.
    pause
    exit /b 1
)

echo [3/3] Gerando o executavel...
python -m PyInstaller --noconsole --onefile --clean --name AutoTile autotile_tray.py
if %errorlevel% neq 0 (
    echo Erro ao gerar o .exe.
    pause
    exit /b 1
)

echo.
echo Pronto! Seu programa esta em: %~dp0dist\AutoTile.exe
echo Pode copiar o AutoTile.exe para onde quiser.
explorer "%~dp0dist"
pause