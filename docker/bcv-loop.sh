#!/bin/sh
# Sincroniza tasas BCV a las 09:00 y 15:00 (America/Caracas).
set -e
export TZ="${TZ:-America/Caracas}"
exec python - <<'PY'
import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo

tz = ZoneInfo("America/Caracas")
last = None
while True:
    now = datetime.now(tz)
    slot = (now.hour, now.minute)
    if slot in ((9, 0), (15, 0)) and last != (now.date(), slot):
        last = (now.date(), slot)
        subprocess.call(["python", "manage.py", "bcv", "--strict-window"])
    time.sleep(20)
PY
