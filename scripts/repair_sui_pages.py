"""Reread the transactions of a Sui sample whose inputs or object changes ran past the first page of 50.

An earlier version of sample_sui.py read only the first page, so these transactions lost shared inputs and recorded
others as unchanged.  This rewrites their records in place with all pages; the rest of the sample is left as read.
Identities stay in data/ and are never reported.
Usage: python repair_sui_pages.py [sample.jsonl]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sample_sui as S  # noqa: E402

FIELD = ('effects { objectChanges(first: 50) { pageInfo { hasNextPage } } } '
         'kind { __typename ... on ProgrammableTransaction { inputs(first: 50) { pageInfo { hasNextPage } } } }')


def truncated(rows, batch=20):
    out = set()
    for s in range(0, len(rows), batch):
        part = rows[s:s + batch]
        q = "{ " + " ".join('a%d: transaction(digest: "%s") { %s }' % (i, r["digest"], FIELD) for i, r in enumerate(part)) + " }"
        data = S.gql(q)["data"]
        for i, r in enumerate(part):
            x = data[f"a{i}"]
            if (((x.get("kind") or {}).get("inputs") or {}).get("pageInfo") or {}).get("hasNextPage") \
                    or (((x.get("effects") or {}).get("objectChanges") or {}).get("pageInfo") or {}).get("hasNextPage"):
                out.add(r["digest"])
        time.sleep(0.3)
    return out


def reread(r):
    q = '{ transaction(digest: "%s") { %s } }' % (r["digest"], S.TX_FIELDS)
    fresh = S.reduce(S.gql(q)["data"]["transaction"], r["cp"])
    fresh["t"] = r.get("t")
    return fresh


def main(name):
    path = Path(S.OUT) / name
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    todo = truncated(rows)
    print(len(rows), "transactions,", len(todo), "with a list past the first page", flush=True)
    out = []
    before = after = 0
    for r in rows:
        if r["digest"] in todo:
            f = reread(r)
            assert f["status"] == r["status"]
            before += len(r["shared"])
            after += len(f["shared"])
            r = f
        out.append(r)
    path.write_text("".join(json.dumps(r) + "\n" for r in out), encoding="utf-8")
    print("shared inputs in those transactions:", before, "before,", after, "after", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sui_v2.jsonl")
