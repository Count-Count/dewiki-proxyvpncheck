#!/usr/bin/python
#
# (C) 2020 Count Count
#
# Distributed under the terms of the MIT license.

from __future__ import unicode_literals

import locale
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast, List, Any, Set

import os
import re
import time
import json
import requests

import pytz
import pywikibot


@dataclass
class CheckResult:
    score: int
    cached: bool


class CheckException(Exception):
    pass


class Program:
    def __init__(self) -> None:
        self.site = pywikibot.Site()
        self.site.login()
        self.timezone = pytz.timezone("Europe/Berlin")
        self.apikey = os.getenv("IPCHECK_API_KEY")

    def getAllIps(self, recentChanges) -> Set[str]:
        ips: Set[str] = set()
        for ch in recentChanges:
            if "userhidden" in ch:
                continue
            if (ch["type"] == "edit" or ch["type"] == "new") and "anon" in ch:
                ips.add(ch["user"])
        return ips

    def checkWithIpCheck(self, ip: str) -> CheckResult:
        lastError = None
        for _ in range(5):
            try:
                response = requests.get(f"https://ipcheck.toolforge.org/index.php?ip={ip}&api=true&key={self.apikey}")
                if response.status_code == 200:
                    blockScore = 0
                    errors = 0
                    jsonResponse = json.loads(response.text)
                    if not "error" in jsonResponse["teohio"]:
                        if jsonResponse["teohio"]["result"]["vpnOrProxy"]:
                            blockScore += 1
                    else:
                        errors += 1
                    if not "error" in jsonResponse["proxycheck"]:
                        if jsonResponse["proxycheck"]["result"]["proxy"]:
                            blockScore += 1
                    else:
                        errors += 1
                    if not "error" in jsonResponse["getIPIntel"]:
                        if jsonResponse["getIPIntel"]["result"]["chance"] == 100:
                            blockScore += 1
                    if not "error" in jsonResponse["ipQualityScore"]:
                        if (
                            jsonResponse["ipQualityScore"]["result"]["proxy"]
                            or jsonResponse["ipQualityScore"]["result"]["vpn"]
                        ):
                            blockScore += 1
                    else:
                        errors += 1

                    cached = jsonResponse["cache"]["result"]["cached"] == "yes"
                    return CheckResult(cached=cached, score=blockScore)
                else:
                    response.raise_for_status()
            except Exception as ex:
                lastError = str(ex)
            # delay in case of error
            time.sleep(1)
        else:
            raise CheckException(lastError)

    def listIPs(self) -> None:
        print(f"Retrieving recent changes...")
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

        # ipsWithMoreThanTwoReverts = set(
        #     [ip for (ip, count) in ipToRevertCount.items() if count >= 3 and not ip in shortlyBlockedIps]
        # )
        # for ip in ipsWithMoreThanTwoReverts:
        #     print(f"https://de.wikipedia.org/wiki/Spezial:Beitr%C3%A4ge/{ip}")
        # print(f"IPs with more than two reverts: {len(ipsWithMoreThanTwoReverts)}")
        print(f"Blocked ips: {len(shortlyBlockedIps)}")
        ips = set(shortlyBlockedIps).union(reportedIps)
        print(f"Reported ips: {len(reportedIps)}")
        print(f"Reported but not blocked ips: {len(ips) - len(shortlyBlockedIps)}")
        print(f"Checking {len(ips)} addresses...")

        uncached = 0
        # ips = ["103.224.240.72"]
        for ip in ips:
            try:
                checkRes = self.checkWithIpCheck(ip)
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
