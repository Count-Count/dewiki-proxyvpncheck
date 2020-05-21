#!/bin/bash
set -euxo pipefail

(cd ../; pipenv lock --requirements > /tmp/requirements.txt)

pscp /tmp/requirements.txt ../{sentinel.py,vpncheck.py,sseclient.py} deploy.sh exec-bot.sh *.yaml countcount@login.tools.wmflabs.org:/data/project/dewikivpncheck/
pscp ../user-config.py countcount@login.tools.wmflabs.org:/data/project/dewikivpncheck/user-config.py.orig
plink countcount@login.tools.wmflabs.org "chmod 755 /data/project/dewikivpncheck/exec-bot.sh"
plink countcount@login.tools.wmflabs.org "chmod 755 /data/project/dewikivpncheck/deploy.sh"
plink countcount@login.tools.wmflabs.org "become dewikivpncheck cp /data/project/dewikivpncheck/user-config.py.orig /data/project/dewikivpncheck/user-config.py"
plink countcount@login.tools.wmflabs.org "become dewikivpncheck /data/project/dewikivpncheck/deploy.sh"
