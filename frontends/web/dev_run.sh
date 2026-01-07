#!/bin/bash
# Stegasoo Web Frontend - Development Runner
# Press 'r' to restart, 'q' to quit (single keypress, no Enter needed)

cd "$(dirname "$0")"

PID=""

cleanup() {
    echo -e "\n\033[33mShutting down...\033[0m"
    [[ -n "$PID" ]] && kill "$PID" 2>/dev/null
    stty sane 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

start_server() {
    clear
    echo -e "\033[36m┌──────────────────────────────────────┐\033[0m"
    echo -e "\033[36m│  Stegasoo Dev Server                 │\033[0m"
    echo -e "\033[36m│  \033[0m[r] restart  [q] quit\033[36m              │\033[0m"
    echo -e "\033[36m└──────────────────────────────────────┘\033[0m"

    pkill -f "python app.py" 2>/dev/null
    sleep 0.3

    python app.py 2>&1 &
    PID=$!
    echo -e "\033[32m✓ Running on http://localhost:5000 (PID: $PID)\033[0m\n"
}

start_server

# Single keypress mode
stty -echo -icanon time 0 min 0

while true; do
    key=$(dd bs=1 count=1 2>/dev/null)
    case "$key" in
        r|R) start_server ;;
        q|Q) cleanup ;;
    esac

    # Check if crashed
    if [[ -n "$PID" ]] && ! kill -0 "$PID" 2>/dev/null; then
        echo -e "\033[31m✗ Crashed! Press 'r' to restart\033[0m"
        PID=""
    fi

    sleep 0.1
done
