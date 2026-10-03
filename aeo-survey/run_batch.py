#!/usr/bin/env python3
"""Run one sub-agent's question variants against every answer engine.

Each sub-agent gets its own agent-browser sessions (aeo-<agent>-<engine>), so
browsers, cookies and storage never leak between agents or engines. Results are
appended to results/raw/<agent>.jsonl; re-running skips pairs already answered.

Usage:
    python3 run_batch.py --agent A [--engines chatgpt,gemini,perplexity] [--mock URL]
    python3 run_batch.py --agent A --question-ids A2 --engines gemini   # retry one pair
"""
import argparse
import json
import os
from pathlib import Path

from ask_engine import Browser, ask

HERE = Path(__file__).resolve().parent
QUESTIONS = json.loads((HERE / "questions.json").read_text())


def load_done(path):
    done = set()
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("status") == "ok":
                    done.add((r["question_id"], r["engine"]))
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", required=True, choices=[g["id"] for g in QUESTIONS["agents"]])
    ap.add_argument("--engines", default=",".join(QUESTIONS["engines"]))
    ap.add_argument("--question-ids", default=None, help="comma-separated subset, e.g. A1,A3")
    ap.add_argument("--out", default=str(HERE / "results" / "raw"))
    ap.add_argument("--mock", default=None, help="base URL serving mocks/ (offline self-test)")
    ap.add_argument("--force", action="store_true", help="re-ask pairs that already have an ok answer")
    a = ap.parse_args()

    group = next(g for g in QUESTIONS["agents"] if g["id"] == a.agent)
    variants = group["variants"]
    if a.question_ids:
        keep = set(a.question_ids.split(","))
        variants = [v for v in variants if v["id"] in keep]
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{a.agent}{'.mock' if a.mock else ''}.jsonl"
    done = set() if a.force else load_done(out)
    shots = HERE / "results" / "screenshots" / a.agent

    for engine in a.engines.split(","):
        session = f"aeo-{a.agent}-{engine}"
        # Optional auth state exported from the user's own browser, e.g. AEO_STATE_GEMINI=/path/auth.json
        state = os.environ.get(f"AEO_STATE_{engine.upper()}")
        try:
            for v in variants:
                if (v["id"], engine) in done:
                    print(f"[{a.agent}] skip {v['id']} @ {engine} (already ok)")
                    continue
                print(f"[{a.agent}] asking {v['id']} @ {engine} ...", flush=True)
                res = ask(engine, v["question"], session, state=state, mock=a.mock,
                          shot=str(shots / f"{v['id']}-{engine}.png"))
                res = {"agent": a.agent, "angle": group["angle"], "question_id": v["id"],
                       "unbranded": bool(v.get("unbranded")), **res}
                with out.open("a") as f:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
                print(f"[{a.agent}] {v['id']} @ {engine}: {res['status']}"
                      f" ({len(res['answer'])} chars, {len(res['sources'])} sources)"
                      + (f" - {res['error']}" if res["error"] else ""), flush=True)
                if res["status"] in ("blocked_network", "login_required", "challenge"):
                    print(f"[{a.agent}] {engine} is unusable from this sandbox ({res['status']}); skipping its remaining questions")
                    for rest in variants[variants.index(v) + 1:]:
                        if (rest["id"], engine) in done:
                            continue
                        skipped = {**res, "question_id": rest["id"], "question": rest["question"],
                                   "unbranded": bool(rest.get("unbranded")), "answer": "", "sources": [],
                                   "error": f"not attempted: {engine} already returned {res['status']}"}
                        skipped.pop("screenshot", None)
                        with out.open("a") as f:
                            f.write(json.dumps(skipped, ensure_ascii=False) + "\n")
                    break
        finally:
            Browser(session).close()
    print(f"[{a.agent}] wrote {out}")


if __name__ == "__main__":
    main()
