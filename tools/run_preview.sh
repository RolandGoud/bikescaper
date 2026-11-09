#!/bin/sh
# On the NAS: score every ad in the running Bikecheck container with the old and the stricter rules
# (tools/score_preview.py, read-only) and leave the result in /tmp/preview.json on the NAS.
#   curl -fsSL https://raw.githubusercontent.com/RolandGoud/bikescaper/stricter-scores/tools/run_preview.sh | sudo sh
set -e
docker exec bikecompare sh -c 'mkdir -p /tmp/preview && cd /tmp/preview && python -c "
import urllib.request as u
b = \"https://raw.githubusercontent.com/RolandGoud/bikescaper/stricter-scores/tools/\"
for f in (\"score_preview.py\", \"scores_new.py\"):
    u.urlretrieve(b + f, f)
" && cd /app && python /tmp/preview/score_preview.py /data/bikecompare.sqlite3 > /tmp/preview/preview.json'
docker cp bikecompare:/tmp/preview/preview.json /tmp/preview.json
chmod 644 /tmp/preview.json
docker exec bikecompare rm -rf /tmp/preview
echo "Done: $(wc -c < /tmp/preview.json) bytes in /tmp/preview.json"
