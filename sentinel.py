#!/usr/bin/python
#
# (C) 2020 Count Count
#
# Distributed under the terms of the MIT license.

from typing import Any, Tuple, List, Optional, cast, Iterator, Callable, Pattern, Dict
from datetime import datetime
from datetime import timedelta
import os
import re
import time
import signal
import locale
import traceback
import pywikibot
from pywikibot.bot import SingleSiteBot
from pywikibot.diff import PatchManager
from pywikibot.comms.eventstreams import site_rc_listener
from vpncheck import CheckException, VpnCheck


TIMEOUT = 600  # We expect at least one rc entry every 10 minutes


class ReadingRecentChangesTimeoutError(Exception):
    pass


def on_timeout(signum: Any, frame: Any) -> None:
    raise ReadingRecentChangesTimeoutError


class Controller(SingleSiteBot):
    def __init__(self) -> None:
        site = pywikibot.Site()
        site.login()
        super(Controller, self).__init__(site=site)
        self.generator = FaultTolerantLiveRCPageGenerator(self.site)
        self.rollbackRegex = re.compile(r"Änderungen von \[\[(?:Special:Contributions|Spezial:Beiträge)/([^|]+)\|.+")
        self.undoRegex = re.compile(r"Änderung [0-9]+ von \[\[Special:Contribs/([^|]+)\|.+")
        self.vpnCheck = VpnCheck()

    def setup(self) -> None:
        """Setup the bot."""
        if os.name != "nt":
            signal.signal(signal.SIGALRM, on_timeout)  # pylint: disable=E1101
            signal.alarm(TIMEOUT)  # pylint: disable=E1101

    def skip_page(self, page: pywikibot.Page) -> bool:
        """Skip special/media pages"""
        if page.namespace() < 0:
            return True
        elif not page.exists():
            return True
        elif page.isRedirectPage():
            return True
        return super().skip_page(page)

    def treat(self, page: pywikibot.Page) -> None:
        """Process a single Page object from stream."""
        ch = page._rcinfo

        ts = datetime.fromtimestamp(ch["timestamp"])

        if datetime.now() - ts > timedelta(minutes=5):
            pywikibot.warning("Change too old: %s" % (str(datetime.now() - ts)))
            return

        if os.name != "nt":
            signal.alarm(TIMEOUT)  # pylint: disable=E1101

        if ch["type"] == "edit":
            comment = ch["comment"]
            rollbackedUser = None
            searchRes1 = self.rollbackRegex.search(comment)
            if searchRes1:
                rollbackedUser = searchRes1.group(1)
            searchRes2 = self.undoRegex.search(comment)
            if searchRes2:
                rollbackedUser = searchRes2.group(1)
            if rollbackedUser:
                pyUser = pywikibot.User(self.site, rollbackedUser)
                if pyUser.isAnonymous():
                    ip = rollbackedUser
                    pywikibot.output(f"IP reverted: {ip}")
                    try:
                        checkRes = self.vpnCheck.checkWithTeoh(ip)
                        if checkRes.score >= 2:
                            checkRes = self.vpnCheck.checkWithIpCheck(ip)
                    except CheckException as ex:
                        print(f"{ip} could not be checked: {ex}")
                    else:
                        if checkRes.score >= 2:
                            print(f"Likely VPN or proxy: {ip}, score: {checkRes.score}")

    def teardown(self) -> None:
        """Bot has finished due to unknown reason."""
        if self._generator_completed:
            pywikibot.log("Main thread exit - THIS SHOULD NOT HAPPEN")
            time.sleep(10)


def FaultTolerantLiveRCPageGenerator(site: pywikibot.site.BaseSite) -> Iterator[pywikibot.Page]:
    for entry in site_rc_listener(site):
        # The title in a log entry may have been suppressed
        if "title" not in entry and entry["type"] == "log":
            continue
        try:
            page = pywikibot.Page(site, entry["title"], entry["namespace"])
        except Exception:
            pywikibot.warning("Exception instantiating page %s: %s" % (entry["title"], traceback.format_exc()))
            continue
        page._rcinfo = entry
        yield page


def main() -> None:
    locale.setlocale(locale.LC_ALL, "de_DE.utf8")
    pywikibot.handle_args()
    Controller().run()


if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()
