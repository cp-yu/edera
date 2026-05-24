#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

BACKEND_PORT=8000
FRONTEND_PORT=5173

kill_port() {
    local pid
    pid=$(lsof -t -i:"$1" 2>/dev/null) || true
    [ -n "$pid" ] && kill $pid 2>/dev/null && echo "Stopped port $1 (pid: $pid)" || true
}

case "${1:-start}" in
    start)
        kill_port $BACKEND_PORT
        kill_port $FRONTEND_PORT
        .venv/bin/python -c "from stockimformation_core.main import main; main()" &
        (cd apps/web-console && npm run dev) &
        wait
        ;;
    restart)
        echo "Restarting..."
        kill_port $BACKEND_PORT
        kill_port $FRONTEND_PORT
        sleep 1
        .venv/bin/python -c "from stockimformation_core.main import main; main()" &
        (cd apps/web-console && npm run dev) &
        wait
        ;;
    stop)
        kill_port $BACKEND_PORT
        kill_port $FRONTEND_PORT
        echo "Stopped."
        ;;
    *)
        echo "Usage: $0 {start|restart|stop}"
        exit 1
        ;;
esac
