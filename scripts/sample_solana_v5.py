"""Solana sample, record format v5 (2026-11-02): v4 plus the tip each transaction paid outside the protocol.

Per transaction `tip` is the net lamports it moved to the block engine's public tip accounts, 0 if none.  Responses are requested
gzip-compressed and records are stored as gzip members, one per block, so an interrupted run can resume.

Usage: python sample_solana_v5.py <slots.jsonl | range:FIRST:LAST | every:LAST:N:SPACING> <out.jsonl.gz> <rpc_url> [pause_seconds]
"""
import gzip
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sample_solana_v4 as V4  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data"
TIP_ACCOUNTS = {
    "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
    "HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe",
    "Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY",
    "ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49",
    "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
    "ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt",
    "DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL",
    "3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT",
}


def rpc(url, method, params, timeout=180, tries=8):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    wait = 3
    for t in range(tries):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Accept-Encoding": "gzip",
                                                              "User-Agent": "research-probe/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode()), len(raw)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, EOFError, OSError) as e:
            code = getattr(e, "code", None)
            if t < tries - 1 and (code in (429, 500, 502, 503, 504) or code is None):
                time.sleep(wait)
                wait = min(wait * 2, 60)
                continue
            raise


def tip_of(tx):
    meta = tx["meta"]
    keys = tx["transaction"]["message"]["accountKeys"]
    loaded = meta.get("loadedAddresses") or {"writable": [], "readonly": []}
    all_keys = keys + loaded.get("writable", []) + loaded.get("readonly", [])
    pre, post = meta["preBalances"], meta["postBalances"]
    return sum(post[i] - pre[i] for i, k in enumerate(all_keys) if k in TIP_ACCOUNTS and i < len(pre) and i < len(post))


def slots_from(spec):
    if spec.startswith("range:"):
        _, first, last = spec.split(":")
        return list(range(int(first), int(last) + 1))
    if spec.startswith("every:"):
        _, last, n, spacing = spec.split(":")
        return [int(last) - k * int(spacing) for k in range(int(n))]
    return [json.loads(line)["slot"] for line in open(OUT / spec, encoding="utf-8")]


def main(spec, out_name, url, pause=0.5):
    slots = slots_from(spec)
    path = OUT / out_name
    done = set()
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            try:
                for line in fh:
                    done.add(json.loads(line)["slot"])
            except (EOFError, gzip.BadGzipFile, json.JSONDecodeError):
                pass
    t0 = time.time()
    got = 0
    for k, slot in enumerate(slots):
        if slot in done:
            continue
        try:
            r, size = rpc(url, "getBlock", [slot, {"encoding": "json", "maxSupportedTransactionVersion": 1, "transactionDetails": "full", "rewards": False}])
        except Exception as e:
            print("slot", slot, "error", repr(e)[:160], flush=True)
            time.sleep(5)
            continue
        blk = r.get("result")
        if not blk:
            print("slot", slot, "empty", str(r.get("error"))[:120], flush=True)
            time.sleep(pause)
            continue
        recs = []
        for tx in blk["transactions"]:
            x = V4.reduce_tx(tx, slot, blk.get("blockTime"))
            if x:
                x["tip"] = tip_of(tx)
                recs.append(x)
        line = json.dumps({"slot": slot, "t": blk.get("blockTime"), "n_all": len(blk["transactions"]), "txs": recs}) + "\n"
        with gzip.open(path, "at", encoding="utf-8") as fh:
            fh.write(line)
        got += 1
        print("block", k + 1, "of", len(slots), slot, len(recs), f"{size / 1e6:.1f}MB", f"{(time.time() - t0) / got:.1f}s/block", flush=True)
        time.sleep(pause)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 0.5)
