#!/bin/bash
set -euxo pipefail
echo $(date) Script started...
source /data/project/dewikivpncheck/secret-env.sh
exec /data/project/dewikivpncheck/venv/bin/python /data/project/dewikivpncheck/sentinel.py -v -log:vpncheck.log --run-bot
