"""Run the analyses on the whole minutes of blocks, a process per analysis per minute, skipping what is done (2026-11-02).

Minutes come from results/facts_windows_plan.json, the three windows of November 1 extended to 300 slots each.  A minute's name
is w01, w02, ... for the busiest, in order of transactions per second, and m01, ... for those at the median.

Usage: python run_minutes.py <processes> [name ...]
"""
import gzip
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / "scripts"
RESULTS = BASE / "results"


def minutes():
    plan = json.loads((RESULTS / "facts_windows_plan.json").read_text(encoding="utf-8"))
    busy = json.loads((RESULTS / "facts_busy_minutes.json").read_text(encoding="utf-8"))["windows"]
    peaks = [(w["tps"], w["name"]) for w in plan if w["kind"] == "peak"]
    for tag, w in zip(("c1", "c2", "c3"), busy):
        peaks.append((w["tps"], f"solana_{tag}_v4.jsonl+solana_{tag}x.jsonl.gz"))
    out = {f"w{i + 1:02d}": name for i, (_, name) in enumerate(sorted(peaks, key=lambda x: -x[0]))}
    medians = sorted((w["tps"], w["name"]) for w in plan if w["kind"] == "median")
    out.update({f"m{i + 1:02d}": name for i, (_, name) in enumerate(medians)})
    return out


def jobs_for(names):
    jobs = []
    for tag, sample in names.items():
        jobs += [(f"paper_numbers_{tag}.json", ["analyze_paper_numbers.py", sample]),
                 (f"paper_extensions_{tag}.json", ["analyze_extensions.py", sample]),
                 (f"occupancy_{tag}.json", ["analyze_occupancy.py", sample]),
                 (f"soft_last_{tag}.json", ["analyze_soft_last.py", sample]),
                 (f"reads_{tag}.json", ["analyze_reads.py", sample]),
                 (f"hold_{tag}.json", ["analyze_hold.py", sample]),
                 (f"failed_only_{tag}.json", ["analyze_failed_only.py", sample]),
                 (f"frontier_{tag}.json", ["analyze_frontier.py", sample, f"paper_extensions_{tag}.json"])]
    return jobs


def command(out, spec):
    script, *args = spec
    if script == "analyze_reads.py":
        return [sys.executable, str(SCRIPTS / script), args[0], out, "4", "16"]
    if script == "analyze_frontier.py":
        return [sys.executable, str(SCRIPTS / script), args[0], args[1], out]
    return [sys.executable, str(SCRIPTS / script), args[0], out]


def sample_ready(sample):
    """A file still being fetched is not ready: it has to have stopped growing, with most of its slots in it."""
    plan = {w["name"]: w for w in json.loads((RESULTS / "facts_windows_plan.json").read_text(encoding="utf-8"))}
    log = BASE / "data" / "fetch_windows_log.txt"
    done = log.exists() and "done {" in log.read_text(encoding="utf-8", errors="ignore")
    for part in sample.split("+"):
        path = BASE / "data" / part
        if not path.exists():
            return False
        if part not in plan or done:
            continue
        if time.time() - path.stat().st_mtime < 120:
            return False
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            lines = sum(1 for _ in fh)
        if lines < 0.97 * (plan[part]["last"] - plan[part]["first"] + 1):
            return False
    return True


def main(procs, wanted):
    names = minutes()
    if wanted:
        names = {k: v for k, v in names.items() if k in wanted}
    print(json.dumps(names, indent=1), flush=True)
    (RESULTS / "facts_minutes.json").write_text(json.dumps(minutes(), indent=1), encoding="utf-8")
    pending = [j for j in jobs_for(names) if not (RESULTS / j[0]).exists()]
    env = dict(os.environ, DF_LIGHT="1", PYTHONUNBUFFERED="1")
    running = []
    t0 = time.time()
    log_dir = BASE / "data" / "minutes_logs"
    log_dir.mkdir(exist_ok=True)
    ready_samples = set()
    while pending or running:
        running = [r for r in running if r[0].poll() is None or print(r[1], "exit", r[0].returncode, f"{time.time() - t0:.0f}s", flush=True)]
        if len(running) < procs:
            for sample in {j[1][1] for j in pending} - ready_samples:
                if sample_ready(sample):
                    ready_samples.add(sample)
                    print("ready", sample, flush=True)
        ready = [j for j in pending if j[1][1] in ready_samples and not (j[1][0] == "analyze_frontier.py" and not (RESULTS / j[1][2]).exists())]
        while ready and len(running) < procs:
            job = ready.pop(0)
            pending.remove(job)
            out, spec = job
            with open(log_dir / (out + ".log"), "w", encoding="utf-8") as fh:
                running.append((subprocess.Popen(command(out, spec), stdout=fh, stderr=subprocess.STDOUT, env=env), out))
            print("start", out, "left", len(pending), flush=True)
        time.sleep(5)
    print("done", f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), set(sys.argv[2:]))
