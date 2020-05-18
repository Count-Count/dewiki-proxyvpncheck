#!/usr/bin/python
#
# (C) 2020 Count Count
#
# Distributed under the terms of the MIT license.

from __future__ import unicode_literals

import json
import os
import time
from dataclasses import dataclass

import lmdb
import requests


@dataclass
class CheckResult:
    score: int
    cached: bool


class CheckException(Exception):
    pass


class QuotaExceededException(CheckException):
    pass


class VpnCheck:
    def __init__(self) -> None:
        self.apikey = os.getenv("IPCHECK_API_KEY")
        self.teohCacheEnv = lmdb.open(
            "teohCache", map_size=int(1e8), metasync=False, sync=False, lock=False, writemap=False, meminit=False
        )

    def checkWithTeoh(self, ip: str) -> CheckResult:
        if ip.startswith("2001:16B8:"):
            return CheckResult(score=0, cached=True)
        jsonResponse = None
        cached = False
        with self.teohCacheEnv.begin(buffers=True) as txn:
            getRes = txn.get(ip.encode("utf-8"), None)
            if getRes:
                cached = True
                jsonResponse = json.loads(str(getRes, "utf-8"))
        lastError = None
        if not jsonResponse:
            for _ in range(5):
                try:
                    response = requests.get(f"https://ip.teoh.io/api/vpn/{ip}")
                    if response.status_code == 200:
                        jsonResponse = json.loads(response.text)
                        if not "vpn_or_proxy" in jsonResponse:
                            if "message" in jsonResponse:
                                if jsonResponse["message"].find("Exceeded limit"):
                                    raise QuotaExceededException("Teoh check failed: Quota exceeded")
                                else:
                                    raise CheckException(f"Teoh check failed: {jsonResponse['message']}")
                            else:
                                raise CheckException(f"Teoh check failed: Unknown error")
                        with self.teohCacheEnv.begin(buffers=True, write=True) as txn:
                            txn.put(ip.encode("utf-8"), response.text.encode("utf-8"))
                        break
                except CheckException:
                    raise
                except Exception as ex:
                    lastError = str(ex)
                # delay in case of error
                time.sleep(1)
            else:
                raise CheckException(lastError)
        score = 2 if jsonResponse["vpn_or_proxy"] != "no" else 0
        return CheckResult(score=score, cached=cached)

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

        raise CheckException(lastError)
