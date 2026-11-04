"""Solana sample, record format v4 (2026-11-01).

Differences from the earlier record format (v3):
- the default compute limit follows the client: 3,000 per builtin instruction (the compute-budget
  instruction included) plus 200,000 per other instruction, capped at 1,400,000; an explicit limit is
  capped at 1,400,000 too;
- the priority fee uses that limit, so it matches meta.fee for transactions with a price and no limit;
- each transaction also records its read-only account keys (`ro`) and its number of signatures (`sig`).

Per writable account: [key, signer, token, token_or_lamport_changed, inner_ref, top_router_only], as in v3.
Identities stay in data/ and are never reported.

Usage: python sample_solana_v4.py <slots_from.jsonl | fresh:N:SPACING> <out.jsonl> [rpc_url]
"""
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data"
DEFAULT_RPC = "https://api.mainnet-beta.solana.com"
COMPUTE_BUDGET = "ComputeBudget111111111111111111111111111111"
VOTE = "Vote111111111111111111111111111111111111111"
PLUMBING = {
    "11111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    COMPUTE_BUDGET,
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo",
}
# builtins-default-costs (non-migrating entries and the vote program)
BUILTINS = {
    "11111111111111111111111111111111",              # system
    COMPUTE_BUDGET,
    "BPFLoaderUpgradeab1e11111111111111111111111",
    "BPFLoader1111111111111111111111111111111111",
    "BPFLoader2111111111111111111111111111111111",
    "LoaderV411111111111111111111111111111111111",
    "KeccakSecp256k11111111111111111111111111111",
    "Ed25519SigVerify111111111111111111111111111",
    VOTE,
}
MAX_LIMIT = 1_400_000
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def rpc(url, method, params, timeout=180, tries=10):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    wait = 3
    for t in range(tries):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                              "User-Agent": "research-probe/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError,
                http.client.HTTPException) as e:
            code = getattr(e, "code", None)
            if t < tries - 1 and (code in (429, 500, 502, 503, 504) or code is None):
                time.sleep(wait)
                wait = min(wait * 2, 120)
                continue
            raise


def b58decode(s):
    n = 0
    for ch in s:
        n = n * 58 + B58.index(ch)
    full = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * (len(s) - len(s.lstrip("1"))) + full


def reduce_tx(tx, slot, bt):
    msg = tx["transaction"]["message"]
    meta = tx["meta"]
    keys = msg["accountKeys"]
    loaded = meta.get("loadedAddresses") or {"writable": [], "readonly": []}
    all_keys = keys + loaded.get("writable", []) + loaded.get("readonly", [])
    progs = [all_keys[ix["programIdIndex"]] for ix in msg["instructions"]]
    if VOTE in progs:
        return None
    hdr = msg["header"]
    n = len(keys)
    nsig = hdr["numRequiredSignatures"]
    ro_s = hdr["numReadonlySignedAccounts"]
    ro_u = hdr["numReadonlyUnsignedAccounts"]
    writable = [i for i in range(n) if (i < nsig - ro_s) or (nsig <= i < n - ro_u)]
    writable += list(range(n, n + len(loaded.get("writable", []))))
    wset = set(writable)
    readonly = [all_keys[i] for i in range(len(all_keys)) if i not in wset]
    limit, price, builtin, other = None, 0, 0, 0
    for ix, prog in zip(msg["instructions"], progs):
        if prog in BUILTINS:
            builtin += 1
        else:
            other += 1
        if prog == COMPUTE_BUDGET:
            d = b58decode(ix["data"])
            if d and d[0] == 2 and len(d) >= 5:
                limit = int.from_bytes(d[1:5], "little")
            elif d and d[0] == 3 and len(d) >= 9:
                price = int.from_bytes(d[1:9], "little")
    cfg = msg.get("transactionConfig")
    prio = None
    if tx.get("version") == 1 and cfg is not None:
        limit = cfg.get("computeUnitLimit") or 0
        prio = cfg.get("priorityFee") or 0
    explicit = limit is not None
    if limit is None:
        limit = 3_000 * builtin + 200_000 * other
    limit = min(MAX_LIMIT, limit)
    if prio is None:
        prio = (price * limit + 999_999) // 1_000_000
    inner_refs = set()
    router_top = set()
    for g in meta.get("innerInstructions") or []:
        callee_progs = {all_keys[ix["programIdIndex"]] for ix in g["instructions"]}
        if callee_progs - PLUMBING:
            router_top.add(g["index"])
        for ix in g["instructions"]:
            inner_refs.update(ix["accounts"])
    top_refs = {}
    for ti, ix in enumerate(msg["instructions"]):
        for a in ix["accounts"]:
            top_refs.setdefault(a, set()).add(ti)
    pre, post = meta["preBalances"], meta["postBalances"]
    tpre = {b["accountIndex"]: b["uiTokenAmount"]["amount"] for b in (meta.get("preTokenBalances") or [])}
    tpost = {b["accountIndex"]: b["uiTokenAmount"]["amount"] for b in (meta.get("postTokenBalances") or [])}
    w = []
    for i in writable:
        tok = (i in tpre) or (i in tpost)
        ch = (i < len(pre) and i < len(post) and pre[i] != post[i]) or (tok and tpre.get(i) != tpost.get(i))
        inner = i in inner_refs
        tops = top_refs.get(i, set())
        router_only = (not inner) and bool(tops) and all(ti in router_top for ti in tops)
        w.append([all_keys[i], int(i < nsig), int(tok), int(bool(ch)), int(inner), int(router_only)])
    return {"slot": slot, "t": bt, "v": tx.get("version"), "payer": keys[0],
            "progs": sorted(set(p for p in progs if p != COMPUTE_BUDGET)),
            "limit": limit, "used": meta.get("computeUnitsConsumed") or 0, "cost": meta.get("costUnits"),
            "fee": meta["fee"], "prio": prio, "err": int(meta.get("err") is not None),
            "explicit": int(explicit), "sig": nsig, "w": w, "ro": readonly}


def main(slots_from, out_name, url):
    if slots_from.startswith("fresh:"):
        _, n, spacing = slots_from.split(":")
        top = rpc(url, "getSlot", [{"commitment": "finalized"}])["result"] - 64
        slots = [top - k * int(spacing) for k in range(int(n))]
    else:
        slots = [json.loads(line)["slot"] for line in open(OUT / slots_from, encoding="utf-8")]
    done = set()
    path = OUT / out_name
    if path.exists():
        done = {json.loads(line)["slot"] for line in open(path, encoding="utf-8")}
    with open(path, "a", encoding="utf-8") as fh:
        for k, slot in enumerate(slots):
            if slot in done:
                continue
            try:
                r = rpc(url, "getBlock", [slot, {"encoding": "json", "maxSupportedTransactionVersion": 1,
                                                 "transactionDetails": "full", "rewards": False}])
            except Exception as e:
                print("slot", slot, "error", e, flush=True)
                time.sleep(10)
                continue
            blk = r.get("result")
            if not blk:
                print("slot", slot, "empty", str(r.get("error"))[:120], flush=True)
                continue
            bt = blk.get("blockTime")
            recs = [x for x in (reduce_tx(tx, slot, bt) for tx in blk["transactions"]) if x]
            fh.write(json.dumps({"slot": slot, "t": bt, "n_all": len(blk["transactions"]), "txs": recs}) + "\n")
            fh.flush()
            print("block", k + 1, slot, len(recs), flush=True)
            time.sleep(1.5)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else DEFAULT_RPC)
