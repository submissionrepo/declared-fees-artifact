"""Sui sample: shared objects declared mutable versus actually modified (2026-10-16).

For checkpoints spaced back from
the latest one, fetch up to `per_cp` transactions each through the public
GraphQL endpoint and reduce every programmable transaction to:

  checkpoint, digest, status, sender, gas budget and price, computation cost,
  move-call targets (package::module::function), and for each shared input:
  (address, declared mutable, in objectChanges, contents changed).

A shared object declared mutable is written back with a new version even when
its contents do not change, so it is sequenced as a write; "contents changed"
compares the BCS contents of the input and output states.

Identities stay in data/ and are never reported.
Usage: python sample_sui.py [n_checkpoints] [spacing] [per_cp] [out_name]
"""
import json
import sys
import time
import urllib.error
import urllib.request

OUT = str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data")
URL = "https://graphql.mainnet.sui.io/graphql"
OUTNAME = "sui_sample.jsonl"

CHANGE_FIELDS = """address idCreated idDeleted
      inputState { version owner { __typename ... on ObjectOwner { address { address } } } asMoveObject { contents { bcs } } }
      outputState { version owner { __typename ... on ObjectOwner { address { address } } } asMoveObject { contents { bcs } } }"""

TX_FIELDS = """
  digest
  sender { address }
  gasInput { gasBudget gasPrice }
  kind { __typename ... on ProgrammableTransaction {
      inputs(first: 50) { pageInfo { hasNextPage endCursor } nodes { __typename ... on SharedInput { address mutable } } }
      commands(first: 50) { nodes { __typename ... on MoveCallCommand { function { name module { name package { address } } } } } }
  } }
  effects {
    status
    gasEffects { gasSummary { computationCost storageCost storageRebate } }
    objectChanges(first: 50) { pageInfo { hasNextPage endCursor } nodes { %s } }
  }
""" % CHANGE_FIELDS


def gql(query, tries=8):
    body = json.dumps({"query": query}).encode()
    wait = 2
    for t in range(tries):
        req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json",
                                                              "User-Agent": "research-probe/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read().decode())
            if "errors" in d and not d.get("data"):
                raise RuntimeError(str(d["errors"])[:300])
            return d
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as e:
            if t < tries - 1:
                time.sleep(wait)
                wait = min(wait * 2, 90)
                continue
            raise


def more_pages(digest, conn, first_page):
    """All nodes of a transaction's inputs or object changes, from the first page on."""
    nodes = list(first_page["nodes"])
    info = first_page.get("pageInfo") or {}
    while info.get("hasNextPage"):
        after = 'after: "%s"' % info["endCursor"]
        if conn == "inputs":
            q = ('{ transaction(digest: "%s") { kind { ... on ProgrammableTransaction { inputs(first: 50, %s) { pageInfo { hasNextPage endCursor } '
                 'nodes { __typename ... on SharedInput { address mutable } } } } } } }') % (digest, after)
            page = gql(q)["data"]["transaction"]["kind"]["inputs"]
        else:
            q = ('{ transaction(digest: "%s") { effects { objectChanges(first: 50, %s) { pageInfo { hasNextPage endCursor } nodes { %s } } } } }'
                 % (digest, after, CHANGE_FIELDS))
            page = gql(q)["data"]["transaction"]["effects"]["objectChanges"]
        nodes += page["nodes"]
        info = page.get("pageInfo") or {}
        time.sleep(0.3)
    return nodes


def reduce(n, cp):
    k = n.get("kind") or {}
    if k.get("__typename") != "ProgrammableTransaction":
        return None
    inputs = more_pages(n["digest"], "inputs", k.get("inputs") or {"nodes": []})
    shared = [x for x in inputs if x["__typename"] == "SharedInput"]
    calls = []
    for c in (k.get("commands") or {}).get("nodes", []):
        if c["__typename"] == "MoveCallCommand" and c.get("function"):
            f = c["function"]
            calls.append(f"{f['module']['package']['address'][:18]}::{f['module']['name']}::{f['name']}")
    eff = n.get("effects") or {}
    ch = {}
    child_owners = []          # owner addresses of changed objects owned by another object (dynamic fields)
    for c in more_pages(n["digest"], "objectChanges", eff.get("objectChanges") or {"nodes": []}):
        a = ((c.get("inputState") or {}).get("asMoveObject") or {}).get("contents") or {}
        b = ((c.get("outputState") or {}).get("asMoveObject") or {}).get("contents") or {}
        ch[c["address"]] = (a.get("bcs") is not None and b.get("bcs") is not None, a.get("bcs") != b.get("bcs"))
        for st in ("inputState", "outputState"):
            o = ((c.get(st) or {}).get("owner") or {})
            if o.get("__typename") == "ObjectOwner":
                child_owners.append(((o.get("address") or {}).get("address")))
                break
    sh = []
    for s in shared:
        present, changed = ch.get(s["address"], (False, False))
        sh.append([s["address"], int(bool(s["mutable"])), int(present), int(bool(changed))])
    gs = ((eff.get("gasEffects") or {}).get("gasSummary") or {})
    gi = n.get("gasInput") or {}
    return {"cp": cp, "digest": n["digest"], "status": eff.get("status"),
            "sender": (n.get("sender") or {}).get("address"),
            "budget": gi.get("gasBudget"), "price": gi.get("gasPrice"),
            "comp": gs.get("computationCost"), "calls": sorted(set(calls)), "shared": sh,
            "child_owners": sorted(set(x for x in child_owners if x))}


def main(n_cp, spacing, per_cp):
    latest = gql("{ checkpoint { sequenceNumber } }")["data"]["checkpoint"]["sequenceNumber"] - 20
    with open(f"{OUT}/{OUTNAME}", "a", encoding="utf-8") as fh:
        for i in range(n_cp):
            cp = latest - i * spacing
            q = "{ checkpoint(sequenceNumber: %d) { sequenceNumber timestamp transactions(first: %d) { nodes { %s } } } }" % (
                cp, per_cp, TX_FIELDS)
            try:
                d = gql(q)
            except Exception as e:
                print("cp", cp, "error", e, flush=True)
                continue
            c = (d.get("data") or {}).get("checkpoint")
            if not c:
                continue
            recs = [x for x in (reduce(n, cp) for n in c["transactions"]["nodes"]) if x]
            for r in recs:
                r["t"] = c.get("timestamp")
                fh.write(json.dumps(r) + "\n")
            fh.flush()
            print("checkpoint", i + 1, cp, len(recs), flush=True)
            time.sleep(1.0)


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    c = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    if len(sys.argv) > 4:
        OUTNAME = sys.argv[4]
    main(a, b, c)
