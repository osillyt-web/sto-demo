@echo off
chcp 65001 >nul
cd /d "%~dp0"
title AvtoTochka - server
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if "%PORT%"=="" set "PORT=8000"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin123"

set "PY="
for %%C in (
  "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  "C:\Python314\python.exe"
  "C:\Python313\python.exe"
  "C:\Python310\python.exe"
) do if not defined PY if exist "%%~C" set "PY=%%~C"

if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
  echo.
  echo  [ОШИБКА] Python не найден на этом компьютере.
  echo  Установите Python 3.10 или новее: https://www.python.org/downloads/
  echo  При установке отметьте галочку "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

rem ---- уже запущен? проверяем живым подключением к порту ----
%PY% -c "import socket,sys; s=socket.socket(); s.settimeout(0.4); sys.exit(0 if s.connect_ex(('127.0.0.1', %PORT%))==0 else 1)"
if not errorlevel 1 (
  echo.
  echo  Сервер уже запущен: http://127.0.0.1:%PORT%/
  echo  Второй раз запускать не нужно - просто закройте это окно.
  start "" "http://127.0.0.1:%PORT%/"
  ping -n 3 127.0.0.1 >nul
  exit /b 0
)

echo.
echo  АвтоТочка - демо СТО/детейлинг
echo  Python:  %PY%
echo  Сайт:    http://127.0.0.1:%PORT%/
echo  Админка: http://127.0.0.1:%PORT%/admin    пароль: %ADMIN_PASSWORD%
echo.
echo  Чтобы остановить сервер - закройте это окно или нажмите Ctrl+C.
echo.

start "" "http://127.0.0.1:%PORT%/"
%PY% server.py

echo.
echo  Сервер остановлен.
pause
