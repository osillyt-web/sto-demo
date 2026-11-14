#!/bin/sh
# Перезапуск Python-приложения сайта (порт 8500). Вызывается вручную при обновлении кода.
cd /home/osillytweb/www || exit 1
mkdir -p data

if [ -f data/app.pid ]; then
    old=$(cat data/app.pid)
    case "$old" in
        ''|*[!0-9]*) : ;;
        *) kill -TERM "$old" 2>/dev/null ;;
    esac
fi

# добиваем все оставшиеся экземпляры приложения (pid-файл мог устареть)
old_pids=$(ps -u "$(id -un)" -o pid,cmd | awk '/[s]erver\.py$/ {print $1}')
for p in $old_pids; do
    kill -TERM "$p" 2>/dev/null
done
[ -n "$old_pids" ] && sleep 3

setsid env PYTHONUTF8=1 python3 server.py > data/app.log 2>&1 < /dev/null &

i=0
while [ $i -lt 30 ]; do
    sleep 0.5
    if curl -s -o /dev/null http://127.0.0.1:8500/api/health; then
        break
    fi
    i=$((i + 1))
done

newpid=$(ps -u "$(id -un)" -o pid,cmd | awk '/[s]erver\.py/ {print $1; exit}')
echo "$newpid" > data/app.pid
echo "pid=$newpid"
curl -s http://127.0.0.1:8500/api/health | head -c 120
echo
curl -s http://127.0.0.1:8500/sitemap.xml | grep -o '<loc>[^<]*</loc>' | head -3
