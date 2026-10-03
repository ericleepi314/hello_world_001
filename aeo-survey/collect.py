#!/usr/bin/env python3
"""Merge every sub-agent's raw results into one file of questions + answers.

Reads results/raw/<agent>.jsonl (the latest record per question/engine wins) and
writes results/answers.json and results/answers.md, with a small AEO scorecard:
does each answer recognise Clawcodex, and which competitors does it name?

Usage:
    python3 collect.py [--mock]   # --mock reads the *.mock.jsonl self-test output instead
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUESTIONS = json.loads((HERE / "questions.json").read_text())
ENGINE_NAMES = {"chatgpt": "ChatGPT", "gemini": "Gemini", "perplexity": "Perplexity"}

UNKNOWN_PATTERNS = [
    r"not (?:aware|familiar) (?:of|with)", r"(?:couldn't|could not|can't|cannot|unable to) find",
    r"no (?:reliable |widely available |specific )?information", r"doesn't appear to be", r"may not exist",
    r"not a (?:widely )?(?:known|recognized)", r"i don't have (?:any )?(?:specific )?information",
    r"isn't widely documented", r"limited (?:public )?information",
]
COMPETITORS = ["Aider", "OpenHands", "OpenDevin", "SWE-agent", "Open Interpreter", "gpt-engineer", "smolagents",
               "Goose", "Codex CLI", "Claude Code", "Gemini CLI", "Cline", "Continue", "Plandex", "Mentat",
               "Cursor", "GitHub Copilot", "Devin", "AutoGPT", "Qwen Code", "OpenCode", "Crush", "Roo Code"]


def score(answer):
    low = answer.lower()
    return {
        "mentions_clawcodex": "clawcodex" in low or "claw codex" in low,
        "says_unknown": any(re.search(p, low) for p in UNKNOWN_PATTERNS),
        "competitors": [c for c in COMPETITORS if re.search(r"(?<![\w-])" + re.escape(c.lower()) + r"(?![\w-])", low)],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    raw = HERE / "results" / "raw"
    files = sorted(raw.glob("*.mock.jsonl" if a.mock else "*.jsonl"))
    if not a.mock:
        files = [f for f in files if not f.name.endswith(".mock.jsonl")]
    latest = {}
    for f in files:
        for line in f.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                key = (r["question_id"], r["engine"])
                # Prefer a later record, but never let a failed retry overwrite a good answer.
                if key not in latest or r["status"] == "ok" or latest[key]["status"] != "ok":
                    latest[key] = r

    engines = QUESTIONS["engines"]
    out = {"product": QUESTIONS["product"], "base_question": QUESTIONS["base_question"],
           "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "mock": a.mock, "questions": []}
    for g in QUESTIONS["agents"]:
        for v in g["variants"]:
            q = {"id": v["id"], "agent": g["id"], "angle": g["angle"], "question": v["question"],
                 "unbranded": bool(v.get("unbranded")), "answers": {}}
            for e in engines:
                r = latest.get((v["id"], e))
                if not r:
                    q["answers"][e] = {"status": "not_run"}
                    continue
                q["answers"][e] = {k: r.get(k) for k in ("status", "answer", "sources", "error", "final_url",
                                                        "started_at", "duration_s", "logged_in", "screenshot")}
                shot = Path(r.get("screenshot") or "")
                # Sub-agents run in throwaway worktrees; keep only screenshots that still exist here.
                q["answers"][e]["screenshot"] = (str(shot.relative_to(HERE)) if shot.is_file() and
                                                 shot.is_relative_to(HERE) else None)
                if r["status"] == "ok":
                    q["answers"][e]["aeo"] = score(r["answer"])
            out["questions"].append(q)

    res_dir = HERE / "results"
    res_dir.mkdir(exist_ok=True)
    stem = "answers.mock" if a.mock else "answers"
    (res_dir / f"{stem}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    (res_dir / f"{stem}.md").write_text(render_md(out, engines))
    print(f"wrote {res_dir / (stem + '.json')} and {res_dir / (stem + '.md')}")


def render_md(out, engines):
    L = [f"# AEO survey: {out['product']}", "",
         f"**Base question:** {out['base_question']}", "",
         f"Generated {out['generated_at']}" + (" from **mock** engines (self-test, not real answers)" if out["mock"] else ""), ""]
    if not any(q["answers"][e]["status"] == "ok" for q in out["questions"] for e in engines):
        L += ["> **No answers collected yet.** See the statuses below; `blocked_network` means the sandbox's "
              "egress policy refused the engine's host (see README, \"Network access the survey needs\").", ""]
    # Scorecard
    L += ["## Scorecard", "", "| Engine | Answered | Mentions Clawcodex | Says it doesn't know Clawcodex | Other statuses |",
          "| --- | --- | --- | --- | --- |"]
    for e in engines:
        rows = [q["answers"][e] for q in out["questions"]]
        ok = [r for r in rows if r["status"] == "ok"]
        other = {}
        for r in rows:
            if r["status"] != "ok":
                other[r["status"]] = other.get(r["status"], 0) + 1
        L.append(f"| {ENGINE_NAMES.get(e, e)} | {len(ok)}/{len(rows)} | {sum(r['aeo']['mentions_clawcodex'] for r in ok)} | "
                 f"{sum(r['aeo']['says_unknown'] for r in ok)} | {', '.join(f'{k}: {v}' for k, v in sorted(other.items())) or '-'} |")
    comp = {}
    for q in out["questions"]:
        for e in engines:
            for c in (q["answers"][e].get("aeo") or {}).get("competitors", []):
                comp[c] = comp.get(c, 0) + 1
    if comp:
        L += ["", "**Competitors named across answers:** " +
              ", ".join(f"{c} ({n})" for c, n in sorted(comp.items(), key=lambda x: -x[1]))]
    L.append("")
    # Questions and answers
    L += ["## Questions and answers", ""]
    for q in out["questions"]:
        L += [f"### {q['id']}: {q['question']}", "",
              f"*Sub-agent {q['agent']}, angle: {q['angle']}{', unbranded' if q['unbranded'] else ''}*", ""]
        for e in engines:
            r = q["answers"][e]
            L.append(f"#### {ENGINE_NAMES.get(e, e)}: `{r['status']}`")
            L.append("")
            if r["status"] == "ok":
                aeo = r["aeo"]
                L.append(f"> Mentions Clawcodex: {'yes' if aeo['mentions_clawcodex'] else 'no'} · "
                         f"Says unknown: {'yes' if aeo['says_unknown'] else 'no'} · "
                         f"Competitors: {', '.join(aeo['competitors']) or 'none'}")
                L += ["", r["answer"].strip(), ""]
                if r.get("sources"):
                    L.append("Sources:")
                    L += [f"- [{(s.get('text') or s['href'])[:100]}]({s['href']})" for s in r["sources"][:20]]
                    L.append("")
            elif r["status"] != "not_run":
                L += [f"Not collected: {r.get('error') or r['status']}", ""]
            else:
                L += ["Not run yet.", ""]
    return "\n".join(L).rstrip() + "\n"


if __name__ == "__main__":
    main()
