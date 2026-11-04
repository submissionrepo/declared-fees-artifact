"""Cap and access-list samples for Monad and Ethereum (2026-10-16).  Discovery data.

Monad: per transaction, gas limit (charged in full), receipt effectiveGasPrice,
  and eth_estimateGas of the same call at the parent block (an upper bound on
  the gas the call needed at the parent state).
Ethereum: per transaction with a non-empty access list, the declared addresses
  and storage keys against eth_createAccessList of the same call at the parent
  block (the set the call touches at the parent state; an approximation, since
  the transaction ran after earlier transactions of its own block), plus gas
  limit and gasUsed for every transaction of the sampled blocks.

Usage: python sample_caps.py monad <n_blocks> <spacing> | ethereum <n_blocks> <spacing>
"""
import json
import sys
import time
import urllib.error
import urllib.request

OUT = str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data")
MON = "https://rpc.monad.xyz"
ETH = "https://ethereum-rpc.publicnode.com"


def rpc(url, method, params, timeout=90, tries=7):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    wait = 2
    for t in range(tries):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                               "User-Agent": "research-probe/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            code = getattr(e, "code", None)
            if t < tries - 1 and (code in (429, 500, 502, 503, 504) or code is None):
                time.sleep(wait)
                wait = min(wait * 2, 60)
                continue
            raise


def monad(n_blocks, spacing, per_block=12):
    top = int(rpc(MON, "eth_blockNumber", [])["result"], 16) - 30
    with open(f"{OUT}/monad_caps.jsonl", "a", encoding="utf-8") as fh:
        for k in range(n_blocks):
            bn = top - k * spacing
            try:
                b = rpc(MON, "eth_getBlockByNumber", [hex(bn), True])["result"]
                rc = rpc(MON, "eth_getBlockReceipts", [hex(bn)])["result"]
            except Exception as e:
                print("monad", bn, "error", e, flush=True)
                continue
            eg = {r["transactionHash"]: (int(r.get("effectiveGasPrice", "0x0"), 16), r.get("status")) for r in rc}
            txs = [t for t in b["transactions"] if t.get("to")][:per_block]
            for tx in txs:
                call = {"from": tx["from"], "to": tx["to"], "data": tx["input"], "value": tx["value"]}
                try:
                    e = rpc(MON, "eth_estimateGas", [call, hex(bn - 1)])
                    est = int(e["result"], 16) if "result" in e else None
                    err = None if "result" in e else (e.get("error") or {}).get("message")
                except Exception as ex:
                    est, err = None, str(ex)[:120]
                price, status = eg.get(tx["hash"], (None, None))
                fh.write(json.dumps({"block": bn, "limit": int(tx["gas"], 16), "estimate": est, "est_err": err,
                                     "price": price, "status": status, "type": tx.get("type"),
                                     "to": tx["to"], "selector": tx["input"][:10],
                                     "n_access": len(tx.get("accessList") or [])}) + "\n")
                time.sleep(0.12)
            fh.flush()
            print("monad", k + 1, bn, len(txs), flush=True)


def ethereum(n_blocks, spacing):
    top = int(rpc(ETH, "eth_blockNumber", [])["result"], 16) - 10
    with open(f"{OUT}/ethereum_caps.jsonl", "a", encoding="utf-8") as fh, \
            open(f"{OUT}/ethereum_access.jsonl", "a", encoding="utf-8") as fa:
        for k in range(n_blocks):
            bn = top - k * spacing
            try:
                b = rpc(ETH, "eth_getBlockByNumber", [hex(bn), True])["result"]
                rc = rpc(ETH, "eth_getBlockReceipts", [hex(bn)])["result"]
            except Exception as e:
                print("eth", bn, "error", e, flush=True)
                continue
            gu = {r["transactionHash"]: (int(r["gasUsed"], 16), r.get("status")) for r in rc}
            for tx in b["transactions"]:
                used, status = gu.get(tx["hash"], (None, None))
                al = tx.get("accessList") or []
                fh.write(json.dumps({"block": bn, "limit": int(tx["gas"], 16), "used": used, "status": status,
                                     "type": tx.get("type"), "n_access": len(al)}) + "\n")
                if al and tx.get("to"):
                    call = {"from": tx["from"], "to": tx["to"], "data": tx["input"], "value": tx["value"],
                            "gas": tx["gas"]}
                    try:
                        c = rpc(ETH, "eth_createAccessList", [call, hex(bn - 1)])
                        got = c.get("result", {}).get("accessList") if "result" in c else None
                        err = None if got is not None else (c.get("error") or {}).get("message")
                    except Exception as ex:
                        got, err = None, str(ex)[:120]
                    dec = {(x["address"].lower(), s.lower()) for x in al for s in (x.get("storageKeys") or [])}
                    deca = {x["address"].lower() for x in al}
                    if got is not None:
                        gk = {(x["address"].lower(), s.lower()) for x in got for s in (x.get("storageKeys") or [])}
                        ga = {x["address"].lower() for x in got}
                    else:
                        gk, ga = None, None
                    rec = {"block": bn, "status": status, "n_addr": len(deca), "n_keys": len(dec), "err": err}
                    if gk is not None:
                        rec.update({"addr_unused": len(deca - ga), "addr_missing": len(ga - deca),
                                    "keys_unused": len(dec - gk), "keys_missing": len(gk - dec),
                                    "touched_addr": len(ga), "touched_keys": len(gk)})
                    fa.write(json.dumps(rec) + "\n")
                    time.sleep(0.15)
            fh.flush()
            fa.flush()
            print("eth", k + 1, bn, len(b["transactions"]), flush=True)
            time.sleep(0.5)


if __name__ == "__main__":
    which = sys.argv[1]
    nb = int(sys.argv[2])
    spc = int(sys.argv[3])
    (monad if which == "monad" else ethereum)(nb, spc)
