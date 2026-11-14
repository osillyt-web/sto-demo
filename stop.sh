#!/bin/sh
# Остановка Python-приложения (для проверки самоподъёма из index.php).
cd /home/osillytweb/www || exit 1
pids=$(ps -u "$(id -un)" -o pid,cmd | awk '/[s]erver\.py$/ {print $1}')
for p in $pids; do
    kill -TERM "$p" 2>/dev/null
done
echo "остановлены: $pids"
