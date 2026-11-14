#!/bin/zsh
# wifi-meter.zsh: run Apple's networkQuality test and append one row to wifi-log.csv.
# Usage: ./wifi-meter.zsh <label>     e.g. ./wifi-meter.zsh before
set -euo pipefail

if (( $# != 1 )) || [[ -z $1 ]]; then
  print -u2 "Usage: ${0:t} <label>   (e.g. before, after)"
  exit 1
fi
label=$1

if ! command -v networkQuality >/dev/null; then
  print -u2 "networkQuality not found. It ships with macOS 12 (Monterey) and later."
  exit 1
fi

log="${0:A:h}/wifi-log.csv"

print "Running networkQuality (about 20 seconds)..."
json=$(networkQuality -c)

# networkQuality -c prints JSON; plutil reads JSON, so no extra tools are needed.
field() { print -r -- "$json" | plutil -extract "$1" raw -o - - 2>/dev/null || print "" }

dl_bps=$(field dl_throughput)
ul_bps=$(field ul_throughput)
rpm=$(field responsiveness)

if [[ -z $dl_bps || -z $ul_bps ]]; then
  print -u2 "Could not read results from networkQuality:"
  print -u2 -- "$json"
  exit 1
fi

download=$(printf "%.1f" $(( dl_bps / 1000000.0 )))
upload=$(printf "%.1f" $(( ul_bps / 1000000.0 )))
[[ -n $rpm ]] && rpm=$(printf "%.0f" $rpm)

time=$(date "+%Y-%m-%d %H:%M:%S")
# Quote the label so commas in it can't break the CSV.
csv_label="\"${label//\"/\"\"}\""

[[ -f $log ]] || print "time,label,download_mbps,upload_mbps,responsiveness_rpm" > $log
print "$time,$csv_label,$download,$upload,$rpm" >> $log

print "Download:       $download Mbps"
print "Upload:         $upload Mbps"
print "Responsiveness: ${rpm:-n/a} RPM"
print "Saved to $log"
