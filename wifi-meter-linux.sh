#!/usr/bin/env bash
# wifi-meter-linux.sh: Linux version of wifi-meter.zsh.
# Measures download, upload and responsiveness against Cloudflare's speed test
# (speed.cloudflare.com) with curl, and appends one row to wifi-log.csv.
# Usage: ./wifi-meter-linux.sh <label>     e.g. ./wifi-meter-linux.sh before
#
# Responsiveness is an approximation of Apple's metric: round trips per minute
# (RPM = 60 / latency in seconds), measured while a download keeps the line busy.
set -euo pipefail

if [[ $# -ne 1 || -z $1 ]]; then
  echo "Usage: $(basename "$0") <label>   (e.g. before, after)" >&2
  exit 1
fi
label=$1

for cmd in curl awk; do
  command -v "$cmd" >/dev/null || { echo "$cmd is required but not installed." >&2; exit 1; }
done

BASE="https://speed.cloudflare.com"
DOWN_BYTES=${DOWN_BYTES:-50000000}   # 50 MB download
UP_BYTES=${UP_BYTES:-20000000}       # 20 MB upload
log="$(cd "$(dirname "$0")" && pwd)/wifi-log.csv"

mbps() { awk -v b="$1" 'BEGIN { printf "%.1f", b * 8 / 1000000 }'; }

check() {
  if ! curl -sS -o /dev/null --max-time 10 "$BASE/__down?bytes=0"; then
    echo "Cannot reach $BASE. Check your connection or the network allowlist." >&2
    exit 1
  fi
}

echo "Running speed test against speed.cloudflare.com (about 20-40 seconds)..."
check

# Download: average speed in bytes/s as reported by curl.
dl_Bps=$(curl -sS -o /dev/null --max-time 60 -w '%{speed_download}' "$BASE/__down?bytes=$DOWN_BYTES")

# Upload: send zeros from a pipe, so no temp file is needed.
ul_Bps=$(head -c "$UP_BYTES" /dev/zero | curl -sS -o /dev/null --max-time 60 \
  -X POST -H 'Content-Type: application/octet-stream' --data-binary @- \
  -w '%{speed_upload}' "$BASE/__up")

# Responsiveness: time small requests while a large download runs in the background.
curl -sS -o /dev/null --max-time 30 "$BASE/__down?bytes=$DOWN_BYTES" &
load_pid=$!
sleep 1
latencies=()
for _ in 1 2 3 4 5 6 7 8; do
  latencies+=("$(curl -sS -o /dev/null --max-time 10 -w '%{time_starttransfer}' "$BASE/__down?bytes=0" || echo "")")
done
kill "$load_pid" 2>/dev/null || true
wait "$load_pid" 2>/dev/null || true

# Median latency in seconds -> RPM.
rpm=$(printf '%s\n' "${latencies[@]}" | awk 'NF && $1 > 0' | sort -n | awk '
  { v[NR] = $1 }
  END {
    if (NR == 0) { print ""; exit }
    m = (NR % 2) ? v[(NR + 1) / 2] : (v[NR / 2] + v[NR / 2 + 1]) / 2
    printf "%.0f", 60 / m
  }')

download=$(mbps "$dl_Bps")
upload=$(mbps "$ul_Bps")
time=$(date "+%Y-%m-%d %H:%M:%S")
csv_label="\"${label//\"/\"\"}\""

[[ -f $log ]] || echo "time,label,download_mbps,upload_mbps,responsiveness_rpm" > "$log"
echo "$time,$csv_label,$download,$upload,$rpm" >> "$log"

echo "Download:       $download Mbps"
echo "Upload:         $upload Mbps"
echo "Responsiveness: ${rpm:-n/a} RPM (approximate)"
echo "Saved to $log"
