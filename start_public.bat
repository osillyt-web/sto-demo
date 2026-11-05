@echo off
chcp 65001 >nul
cd /d "%~dp0"
title АвтоТочка - публичная ссылка для клиента

echo Проверяю сервер на порту 8000...
python -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1',8000))==0 else 1)"
if errorlevel 1 (
  echo Запускаю сервер...
  start "АвтоТочка - сервер" /min cmd /c python server.py
  timeout /t 4 >nul
)

echo Открываю публичную ссылку Cloudflare Tunnel...
echo Ссылка появится ниже строкой https://....trycloudflare.com
echo Ссылка живая, пока открыто это окно и компьютер включён.
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8000 --no-autoupdate
pause
