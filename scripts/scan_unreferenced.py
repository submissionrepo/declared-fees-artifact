"""Writable accounts that no top-level instruction references (2026-11-01).

A program can reach an account only if an instruction passes it, so such a declaration cannot be read or written: a lock
with probability of use zero, the plainest signature of a hold.  Nothing is stored but counts.  Identities are never
reported.

Usage: python scan_unreferenced.py <out.json> <rpc_url> <slots.jsonl> [<slots.jsonl> ...]
Every k-th slot of each list is read, with k given by the environment variable STEP (default 3).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
VOTE = "Vote111111111111111111111111111111111111111"


def rpc(url, method, params, tries=8):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    wait = 3
    for _ in range(tries):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "research-probe/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode())
        except Exception:  # noqa: BLE001
            time.sleep(wait)
            wait = min(wait * 2, 60)
    return {}


def scan(blk, tot):
    for tx in blk["transactions"]:
        msg, meta = tx["transaction"]["message"], tx["meta"]
        keys = list(msg["accountKeys"])
        la = meta.get("loadedAddresses") or {}
        lw, lr = la.get("writable") or [], la.get("readonly") or []
        h = msg["header"]
        nsig, ros, rou = h["numRequiredSignatures"], h["numReadonlySignedAccounts"], h["numReadonlyUnsignedAccounts"]
        ns = len(keys)
        allk = keys + lw + lr
        if any(allk[ix["programIdIndex"]] == VOTE for ix in msg["instructions"]):
            continue
        tot["txs"] += 1
        writable = list(range(nsig, ns - rou)) + list(range(ns, ns + len(lw)))
        readonly = list(range(nsig - ros, nsig)) + list(range(ns - rou, ns)) + list(range(ns + len(lw), len(allk)))
        refs = set()
        for ix in msg["instructions"]:
            refs.add(ix["programIdIndex"])
            refs.update(ix["accounts"])
        u = [i for i in writable if i not in refs]
        tot["writable_nonsigner"] += len(writable)
        tot["writable_unreferenced"] += len(u)
        tot["txs_with_unreferenced_writable"] += bool(u)
        tot["read_only"] += len(readonly)
        tot["read_only_unreferenced"] += sum(i not in refs for i in readonly)


def main(out, url, lists):
    step = int(os.environ.get("STEP", "3"))
    tot = {"blocks": 0, "txs": 0, "writable_nonsigner": 0, "writable_unreferenced": 0, "txs_with_unreferenced_writable": 0, "read_only": 0, "read_only_unreferenced": 0}
    for name in lists:
        slots = [json.loads(line)["slot"] for line in open(DATA / name, encoding="utf-8")][::step]
        for slot in slots:
            r = rpc(url, "getBlock", [slot, {"encoding": "json", "maxSupportedTransactionVersion": 1, "transactionDetails": "full", "rewards": False}])
            if r.get("result"):
                scan(r["result"], tot)
                tot["blocks"] += 1
            print(slot, tot["blocks"], tot["writable_unreferenced"], flush=True)
            time.sleep(1.0)
            Path(out).write_text(json.dumps(tot, indent=1), encoding="utf-8")
    print(json.dumps(tot, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
