#!/bin/bash
set -euxo pipefail

(cd ../; pipenv lock --requirements > /tmp/requirements.txt)

pscp ../{sentinel.py,vpncheck.py,user-config.py} deploy.sh exec-bot.sh *.yaml countcount@login.tools.wmflabs.org:/data/project/dewikivpncheck/
plink countcount@login.tools.wmflabs.org "chmod 755 /data/project/dewikivpncheck/exec-bot.sh"
plink countcount@login.tools.wmflabs.org "chmod 755 /data/project/dewikivpncheck/deploy.sh"
plink countcount@login.tools.wmflabs.org "become dewikivpncheck chown tools.dewikivpncheck /data/project/dewikivpncheck/user-config.py"
plink countcount@login.tools.wmflabs.org "become dewikivpncheck /data/project/dewikivpncheck/deploy.sh"
