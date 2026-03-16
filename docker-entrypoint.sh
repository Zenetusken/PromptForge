#!/usr/bin/env bash
set -e

cd /app/backend
python -m uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000 &
python -m app.mcp_server &

nginx -g 'daemon off;' &

wait -n
exit $?
