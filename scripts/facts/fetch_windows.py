"""Fetch whole minutes of consecutive blocks from several public nodes at once (2026-11-02).

The plan: the busiest minutes in a node's performance records, and minutes at the median of those records, each the 300 slots
that end at the record's slot; and the slots that extend the three windows of November 1 to 300.  Every block goes through
sample_solana_v5's record format into one gzip file per minute.  Only aggregates leave data/.

Usage: python fetch_windows.py <busy_minutes.json> <plan.json> <n_peak> <n_median> <rpc_url> [<rpc_url> ...]
"""
import gzip
import json
import queue
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sample_solana_v4 as V4  # noqa: E402
import sample_solana_v5 as V5  # noqa: E402

BASE = Path(__file__).resolve().parents[2]
DATA = BASE / "data"
WINDOW = 300
MIN_GAP = 2000
EARLIER = {"p01x": 464100763, "p02x": None, "p03x": None}


def make_plan(busy, n_peak, n_median):
    rows = busy["rows"]
    peaks = busy["windows"][:n_peak]
    med = busy["tps_median"]
    chosen = []
    for row in sorted(rows, key=lambda r: abs(r["tps"] - med)):
        if all(abs(row["slot"] - c["slot"]) >= MIN_GAP for c in chosen + peaks):
            chosen.append(row)
        if len(chosen) == 12:
            break
    chosen = sorted(chosen, key=lambda r: r["slot"])
    medians = [chosen[int(i * len(chosen) / n_median)] for i in range(n_median)]
    plan = [{"name": f"solana_p{i + 1:02d}.jsonl.gz", "kind": "peak", "tps": w["tps"], "first": w["slot"] - WINDOW + 1, "last": w["slot"]} for i, w in enumerate(peaks)]
    plan += [{"name": f"solana_m{i + 1:02d}.jsonl.gz", "kind": "median", "tps": w["tps"], "first": w["slot"] - WINDOW + 1, "last": w["slot"]} for i, w in enumerate(medians)]
    return plan


def earlier_windows():
    """The slots that extend the windows of November 1 back to 300 slots each; the file keeps the v4 records for the rest."""
    plan = []
    for tag in ("c1", "c2", "c3"):
        first = min(json.loads(line)["slot"] for line in open(DATA / f"slots_{tag}.jsonl", encoding="utf-8"))
        last = max(json.loads(line)["slot"] for line in open(DATA / f"slots_{tag}.jsonl", encoding="utf-8"))
        plan.append({"name": f"solana_{tag}x.jsonl.gz", "kind": "extension", "first": last - WINDOW + 1, "last": first - 1})
    return plan


def main(busy_path, plan_path, n_peak, n_median, urls):
    busy = json.loads(Path(busy_path).read_text(encoding="utf-8"))
    plan = make_plan(busy, n_peak, n_median) + earlier_windows()
    Path(plan_path).write_text(json.dumps(plan, indent=1), encoding="utf-8")
    jobs = queue.PriorityQueue()    # a slot that failed goes back at its place, so each minute finishes before the next begins
    total = 0
    for order, w in enumerate(plan):
        path = DATA / w["name"]
        done = set()
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                try:
                    for line in fh:
                        done.add(json.loads(line)["slot"])
                except (EOFError, gzip.BadGzipFile, json.JSONDecodeError):
                    pass
        for slot in range(w["first"], w["last"] + 1):
            if slot not in done:
                jobs.put((order, slot, w["name"], 0))
                total += 1
    print("blocks to fetch", total, flush=True)
    lock = threading.Lock()
    stats = {"got": 0, "skipped": 0, "failed": 0, "bytes": 0}
    t0 = time.time()

    def worker(url):
        while True:
            try:
                order, slot, name, tries = jobs.get_nowait()
            except queue.Empty:
                return
            try:
                r, size = V5.rpc(url, "getBlock", [slot, {"encoding": "json", "maxSupportedTransactionVersion": 1, "transactionDetails": "full", "rewards": False}], tries=2)
            except Exception as e:
                if tries < 12:
                    jobs.put((order, slot, name, tries + 1))
                else:
                    with lock:
                        stats["failed"] += 1
                        print("gave up", slot, repr(e)[:120], flush=True)
                time.sleep(2)
                continue
            blk = r.get("result")
            if not blk:
                err = r.get("error") or {}
                if err.get("code") in (-32007, -32009):    # the slot was skipped or is missing from long-term storage
                    with lock:
                        stats["skipped"] += 1
                elif tries < 12:
                    jobs.put((order, slot, name, tries + 1))
                time.sleep(0.2)
                continue
            recs = []
            for tx in blk["transactions"]:
                x = V4.reduce_tx(tx, slot, blk.get("blockTime"))
                if x:
                    x["tip"] = V5.tip_of(tx)
                    recs.append(x)
            line = json.dumps({"slot": slot, "t": blk.get("blockTime"), "n_all": len(blk["transactions"]), "txs": recs}) + "\n"
            with lock:
                with gzip.open(DATA / name, "at", encoding="utf-8") as fh:
                    fh.write(line)
                stats["got"] += 1
                stats["bytes"] += size
                if stats["got"] % 100 == 0:
                    print(stats, f"{(time.time() - t0) / stats['got']:.2f}s/block", "left", jobs.qsize(), flush=True)
            time.sleep(0.2)

    threads = [threading.Thread(target=worker, args=(u,)) for u in urls]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    print("done", stats, f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5:])
