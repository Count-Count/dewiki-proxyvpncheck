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

import pytz
import pywikibot
import requests
import json
from json import JSONDecodeError


@dataclass
class AlreadyReportedCandidates:
    reviewCandidates: Set[str]
    autoReviewCandidates: Set[str]


class Program:
    def __init__(self) -> None:
        self.site = pywikibot.Site()
        self.site.login()
        self.timezone = pytz.timezone("Europe/Berlin")

    def getAllIps(self, recentChanges) -> Set[str]:
        ips: Set[str] = set()
        for ch in recentChanges:
            if "userhidden" in ch:
                continue
            if (ch["type"] == "edit" or ch["type"] == "new") and "anon" in ch:
                ips.add(ch["user"])
        return ips

    def listIPs(self) -> None:
        print(f"Retrieving recent changes...")
        #        h24Ago = datetime.now() - timedelta(days=1)
        startTime = datetime(h24Ago.year, h24Ago.month, h24Ago.day, 0, 0, 0)
        endTime = startTime + timedelta(hours=24)
        recentChanges = list(self.site.recentchanges(end=startTime, start=endTime))  # reverse order
        #        ips = self.getAllIps(recentChanges)

        ips: Set[str] = set()
        rollbackRegex = re.compile(r"Änderungen von \[\[(?:Special:Contributions|Spezial:Beiträge)/([^|]+)\|.+")
        undoRegex = re.compile(r"Änderung [0-9]+ von \[\[Special:Contribs/([^|]+)\|.+")
        for ch in recentChanges:
            if ch["type"] == "edit":
                if "commenthidden" in ch:
                    continue
                comment = ch["comment"]
                if "mw-rollback" in ch["tags"]:
                    searchRes = rollbackRegex.search(comment)
                    if searchRes:
                        user = searchRes.group(1)
                        if pywikibot.User(self.site, user).isAnonymous():
                            ips.add(user)
                elif "mw-undo" in ch["tags"]:
                    searchRes = undoRegex.search(comment)
                    if searchRes:
                        user = searchRes.group(1)
                        if pywikibot.User(self.site, user).isAnonymous():
                            ips.add(user)

        print(f"Checking {len(ips)} addresses...")

        count = 0
        for ip in ips:
            if ip.startswith("2001:16B8:"):
                continue
            for _ in range(5):
                try:
                    response = requests.get(f"https://ip.teoh.io/api/vpn/{ip}")
                    if response.status_code == 200:
                        jsonResponse = json.loads(response.text)
                        if jsonResponse["vpn_or_proxy"] != "no":
                            print(f"{ip} is an open proxy.")
                        break
                except Exception:
                    pass
                # delay in case of error
                time.sleep(1)
            else:
                print(f"{ip} could not be checked (server failure).")

        return


def main() -> None:
    locale.setlocale(locale.LC_ALL, "de_DE.utf8")
    pywikibot.handle_args()
    Program().listIPs()


if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()
