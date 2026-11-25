#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
BR_PORT=${PORT:-3000}
BR_HOST=127.0.0.1
while [ "$#" -gt 0 ]; do
 case "$1" in
  --port) BR_PORT="$2"; shift 2 ;;
  --host) BR_HOST="$2"; shift 2 ;;
  --strictPort) shift ;;
  *) shift ;;
 esac
done
mkdir -p data
# Never commit runtime credentials. One-time local secrets persist across restarts.
if [ ! -f data/local.env ]; then
  python - <<'PY'
import secrets,pathlib
p=pathlib.Path('data/local.env');p.write_text('\n'.join(k+'='+secrets.token_urlsafe(32) for k in ['BR_FOUNDER_TOKEN','BR_AUDIT_TOKEN','BR_OPERATIONS_TOKEN'])+'\n');p.chmod(0o600)
PY
fi
set -a
source data/local.env
set +a
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT
python - <<'PY'
import json
from time import monotonic, sleep
from urllib.request import ProxyHandler, build_opener

opener = build_opener(ProxyHandler({}))
deadline = monotonic() + 30
while monotonic() < deadline:
    try:
        with opener.open("http://127.0.0.1:8000/api/ready", timeout=1) as response:
            if response.status == 200 and json.load(response) == {"status": "ready"}:
                break
    except (OSError, ValueError):
        pass
    sleep(0.2)
else:
    raise SystemExit("Black River API database was not ready within 30 seconds.")
PY
kill -0 "$API_PID"
if [ "$BR_HOST" = "127.0.0.1" ]; then
  export BR_PROXY_AUTH_MODE=local-founder
else
  unset BR_PROXY_AUTH_MODE
fi
./node_modules/.bin/next dev --hostname "$BR_HOST" --port "$BR_PORT"
