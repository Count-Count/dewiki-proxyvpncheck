#!/bin/bash
set -euxo pipefail

BASTION=login.toolforge.org

(cd ../; pipenv lock --requirements > /tmp/requirements.txt)

scp /tmp/requirements.txt ../{sentinel.py,vpncheck.py,sseclient.py} deploy.sh vpncheck-deployment.yaml exec-bot.sh countcount@$BASTION:/data/project/dewikivpncheck/
scp ../user-config.py countcount@$BASTION:/data/project/dewikivpncheck/user-config.py.orig
ssh countcount@$BASTION "chmod 755 /data/project/dewikivpncheck/exec-bot.sh"
ssh countcount@$BASTION "chmod 755 /data/project/dewikivpncheck/deploy.sh"
ssh countcount@$BASTION "become dewikivpncheck cp /data/project/dewikivpncheck/user-config.py.orig /data/project/dewikivpncheck/user-config.py"
ssh countcount@$BASTION "become dewikivpncheck /data/project/dewikivpncheck/deploy.sh"
