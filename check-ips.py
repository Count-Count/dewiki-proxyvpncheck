#!/usr/bin/python
#
# (C) 2020 Count Count
#
# Distributed under the terms of the MIT license.

from __future__ import unicode_literals

import locale
import re
from datetime import datetime, timedelta
from typing import Any, Set

import pytz

import pywikibot
from vpncheck import CheckException, VpnCheck


class Program:
    def __init__(self) -> None:
        self.site = pywikibot.Site()
        self.site.login()
        self.timezone = pytz.timezone("Europe/Berlin")
        self.vpnCheck = VpnCheck()

    def getAllIps(self, recentChanges: Any) -> Set[str]:
        ips: Set[str] = set()
        for ch in recentChanges:
            if "userhidden" in ch:
                continue
            if (ch["type"] == "edit" or ch["type"] == "new") and "anon" in ch:
                ips.add(ch["user"])
        return ips

    def listIPs(self) -> None:
        print("Retrieving recent changes...")
        startTime = datetime.utcnow() - timedelta(hours=24)
        endTime = datetime.utcnow()
        recentChanges = list(self.site.recentchanges(end=startTime, start=endTime))  # reverse order
        #        ips = self.getAllIps(recentChanges)

        reportedIps = set()
        ipToRevertCount = {}
        ipToEditCount = {}
        shortlyBlockedIps = set()
        newUserReportComment = re.compile(r"Neuer Abschnitt /\* Benutzer:(.*) \*/")
        rollbackRegex = re.compile(r"Änderungen von \[\[(?:Special:Contributions|Spezial:Beiträge)/([^|]+)\|.+")
        undoRegex = re.compile(r"Änderung [0-9]+ von \[\[Special:Contribs/([^|]+)\|.+")
        for ch in recentChanges:
            if (ch["type"] == "edit" or ch["type"] == "new") and "anon" in ch:
                if ch["user"] not in ipToEditCount:
                    ipToEditCount[ch["user"]] = 1
                else:
                    ipToEditCount[ch["user"]] += 1
            if ch["type"] == "edit":
                if "commenthidden" in ch:
                    continue
                comment = ch["comment"]
                rollbackedUser = None
                if "mw-rollback" in ch["tags"]:
                    searchRes = rollbackRegex.search(comment)
                    if searchRes:
                        rollbackedUser = searchRes.group(1)
                elif "mw-undo" in ch["tags"]:
                    searchRes = undoRegex.search(comment)
                    if searchRes:
                        rollbackedUser = searchRes.group(1)
                if rollbackedUser:
                    pyUser = pywikibot.User(self.site, rollbackedUser)
                    if pyUser.isAnonymous() and not pyUser.isBlocked():
                        if not rollbackedUser in ipToRevertCount:
                            ipToRevertCount[rollbackedUser] = 1
                        else:
                            ipToRevertCount[rollbackedUser] += 1
                if ch["title"] == "Wikipedia:Vandalismusmeldung":
                    matchRes = newUserReportComment.match(comment)
                    if matchRes:
                        reportedUser = matchRes.group(1)
                        pyUser = pywikibot.User(self.site, reportedUser)
                        if pyUser.isAnonymous():
                            reportedIps.add(reportedUser)
            elif (
                ch["type"] == "log"
                and not "actionhidden" in ch
                and ch["logtype"] == "block"
                and ch["logaction"] == "block"
            ):
                cutoff = datetime.utcnow() + timedelta(days=7)
                if ch["logparams"]["duration"] != "infinity":
                    expiry = datetime.strptime(ch["logparams"]["expiry"], "%Y-%m-%dT%H:%M:%SZ")
                    if expiry < cutoff:
                        pyUser = pywikibot.User(self.site, ch["title"])
                        if pyUser.isAnonymous():
                            shortlyBlockedIps.add(pyUser.username)

        uncached = 0
        print(f"Checking {len(ipToRevertCount.keys())} addresses with teoh...")
        for ip in ipToRevertCount:
            try:
                checkRes = self.vpnCheck.checkWithTeoh(ip)
                if not checkRes.cached:
                    uncached += 1
                if checkRes.score >= 2:
                    checkRes = self.vpnCheck.checkWithIpCheck(ip)
            except CheckException as ex:
                print(f"{ip} could not be checked: {ex}")
            else:
                if checkRes.score >= 2:
                    print(f"Likely VPN or proxy: {ip}, score: {checkRes.score}")
        print(f"Uncached: {uncached}")

        print(f"Blocked ips: {len(shortlyBlockedIps)}")
        ips = set(shortlyBlockedIps).union(reportedIps)
        print(f"Reported ips: {len(reportedIps)}")
        print(f"Reported but not blocked ips: {len(ips) - len(shortlyBlockedIps)}")
        print(f"Checking {len(ips)} addresses...")

        uncached = 0
        # ips = ["103.224.240.72"]
        for ip in ips:
            try:
                checkRes = self.vpnCheck.checkWithIpCheck(ip)
            except CheckException as ex:
                print(f"{ip} could not be checked: {ex}")
            else:
                if checkRes.score >= 2:
                    print(f"Likely VPN or proxy: {ip}, score: {checkRes.score}")
                if not checkRes.cached:
                    uncached += 1

        print(f"Uncached: {uncached}")


def main() -> None:
    locale.setlocale(locale.LC_ALL, "de_DE.utf8")
    pywikibot.handle_args()
    Program().listIPs()


if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()
