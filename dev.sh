#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

SERVER_PORT=9090
WEB_PORT=8000
FRONTEND_PORT=5173

kill_port() {
    local pid
    pid=$(lsof -t -i:"$1" 2>/dev/null) || true
    [ -n "$pid" ] && kill $pid 2>/dev/null && echo "Stopped port $1 (pid: $pid)" || true
}

case "${1:-start}" in
    start)
        kill_port $SERVER_PORT
        kill_port $WEB_PORT
        kill_port $FRONTEND_PORT
        EDERA_DEV=1 EDERA_SERVER_ADDR=127.0.0.1:9090 .venv/bin/edera-server --config-dir ./config &
        EDERA_DEV=1 EDERA_SERVER_ADDR=127.0.0.1:9090 .venv/bin/edera-web &
        (cd apps/web-console && npm run dev) &
        wait
        ;;
    restart)
        "$0" stop
        "$0" start
        ;;
    stop)
        kill_port $SERVER_PORT
        kill_port $WEB_PORT
        kill_port $FRONTEND_PORT
        echo "Stopped."
        ;;
    *)
        echo "Usage: $0 {start|restart|stop}"
        exit 1
        ;;
esac
