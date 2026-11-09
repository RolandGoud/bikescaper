#!/bin/sh
# On the NAS: score every ad in the running Bikecheck container with the old and the stricter rules
# (tools/score_preview.py, read-only) and leave the result as preview.json in your home folder on the NAS.
#   curl -fsSL https://raw.githubusercontent.com/RolandGoud/bikescaper/stricter-scores/tools/run_preview.sh | sudo sh
set -e
OUT="$(eval echo ~${SUDO_USER:-$USER})/preview.json"
C=$(docker ps --format '{{.Names}}' | grep -m1 bikecompare || true)
if [ -z "$C" ]; then
  echo "No running container named bikecompare. Running containers:"; docker ps --format '{{.Names}}  {{.Image}}'
  exit 1
fi
echo "1/3 Container: $C. Downloading the preview script into it..."
docker exec "$C" sh -c 'mkdir -p /tmp/preview && cd /tmp/preview && python -c "
import urllib.request as u
b = \"https://raw.githubusercontent.com/RolandGoud/bikescaper/stricter-scores/tools/\"
for f in (\"score_preview.py\", \"scores_new.py\"):
    u.urlretrieve(b + f, f)
"'
DB=$(docker exec "$C" sh -c 'echo ${BIKECOMPARE_DB:-/data/bikecompare.sqlite3}')
echo "2/3 Scoring every ad in $DB (a few minutes)..."
docker exec -w /app "$C" python /tmp/preview/score_preview.py "$DB" > "$OUT"
docker exec "$C" rm -rf /tmp/preview
chown "${SUDO_USER:-$USER}" "$OUT" 2>/dev/null || true
echo "3/3 Done: $(wc -c < "$OUT") bytes in $OUT"
