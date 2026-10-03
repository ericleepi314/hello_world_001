#!/usr/bin/env python3
"""Ask one answer engine one question through agent-browser and return the answer.

Usage:
    python3 ask_engine.py --engine chatgpt --question "..." [--session NAME] [--mock URL]

Prints a single JSON result object. Statuses:
    ok               answer captured
    blocked_network  the sandbox could not reach the site (egress policy / DNS)
    login_required   the site demands sign-in and no --state was supplied
    challenge        a CAPTCHA / bot check was shown (never solved automatically)
    no_input         page loaded but no prompt box was found (selectors stale?)
    timeout          the answer never finished streaming
    error            anything else (see "error")
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINES = json.loads((HERE / "engines.json").read_text())
COMMON = ENGINES.pop("_common")
ENGINES.pop("_comment", None)

NETWORK_ERRORS = ("ERR_TUNNEL_CONNECTION_FAILED", "ERR_PROXY", "ERR_NAME_NOT_RESOLVED",
                  "ERR_CONNECTION_REFUSED", "ERR_CONNECTION_RESET", "ERR_INTERNET_DISCONNECTED")
DEFAULT_CHROMIUM = "/opt/pw-browsers/chromium"
# Headless Chromium advertises "HeadlessChrome"; present an ordinary desktop Chrome UA instead.
DEFAULT_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/140.0.0.0 Safari/537.36")


class Browser:
    """Thin wrapper over the agent-browser CLI, pinned to one isolated session."""

    def __init__(self, session, state=None, profile=None):
        self.session = session
        self.env = dict(os.environ)
        if Path(DEFAULT_CHROMIUM).exists():
            self.env.setdefault("AGENT_BROWSER_EXECUTABLE_PATH", DEFAULT_CHROMIUM)
        self.env.setdefault("AGENT_BROWSER_ARGS", "--no-sandbox,--disable-dev-shm-usage")
        self.env.setdefault("AGENT_BROWSER_USER_AGENT", DEFAULT_UA)
        self.launch = []
        if state:
            self.launch += ["--state", state]
        if profile:
            self.launch += ["--profile", profile]

    def run(self, *args, timeout=60):
        cmd = ["agent-browser", "--json", "--session", self.session, *self.launch, *args]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=self.env)
        except subprocess.TimeoutExpired:
            return {"success": False, "data": None, "error": f"agent-browser timed out: {args[0]}"}
        out = p.stdout.strip().splitlines()
        for line in reversed(out):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return {"success": False, "data": None, "error": (p.stderr or p.stdout).strip()[-500:]}

    def eval(self, js, timeout=30):
        r = self.run("eval", js, timeout=timeout)
        if not r.get("success"):
            return None
        res = (r.get("data") or {}).get("result")
        if isinstance(res, str):
            try:
                return json.loads(res)
            except json.JSONDecodeError:
                return res
        return res

    def close(self):
        self.run("close", timeout=30)


def js_first_visible(selectors):
    return """(() => {
      const sels = %s;
      for (const s of sels) {
        for (const el of document.querySelectorAll(s)) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) return s;
        }
      }
      return null;
    })()""" % json.dumps(selectors)


def js_dismiss(texts):
    return """(() => {
      const want = %s.map(t => t.toLowerCase());
      const hit = [];
      for (const el of document.querySelectorAll('button, a, [role="button"]')) {
        const t = (el.innerText || el.getAttribute('aria-label') || '').trim().toLowerCase();
        const r = el.getBoundingClientRect();
        if (want.includes(t) && r.width > 0 && r.height > 0) { el.click(); hit.push(t); }
      }
      return hit;
    })()""" % json.dumps(texts)


def js_external_links(own_hosts):
    return """(() => {
      const own = %s;
      const seen = new Set(), out = [];
      for (const a of document.querySelectorAll('a[href^="http"]')) {
        let h; try { h = new URL(a.href).hostname; } catch (e) { continue; }
        if (own.some(o => h === o || h.endsWith('.' + o))) continue;
        if (seen.has(a.href)) continue;
        seen.add(a.href);
        out.push({href: a.href, text: (a.innerText || a.title || '').trim().slice(0, 200)});
      }
      return out;
    })()""" % json.dumps(own_hosts)


def js_state(cfg):
    return """(() => {
      const answerSels = %s, busySels = %s, inputSels = %s;
      let els = [];
      for (const s of answerSels) { els = [...document.querySelectorAll(s)]; if (els.length) break; }
      const last = els[els.length - 1];
      return {
        count: els.length,
        text: last ? last.innerText.trim() : '',
        busy: busySels.some(s => document.querySelector(s)),
        hasInput: inputSels.some(s => document.querySelector(s)),
        url: location.href,
        title: document.title,
        body: (document.body ? document.body.innerText : '').slice(0, 4000)
      };
    })()""" % (json.dumps(cfg["answer"]), json.dumps(cfg["busy"]), json.dumps(cfg["input"]))


def js_input_has(sel, probe):
    return """(() => {
      const el = document.querySelector(%s);
      if (!el) return false;
      const v = (el.value !== undefined && el.tagName === 'TEXTAREA') ? el.value : el.innerText;
      return (v || '').includes(%s);
    })()""" % (json.dumps(sel), json.dumps(probe))


def classify_page(cfg, st):
    """Return a blocking status for the current page, or None if it looks usable."""
    host = re.sub(r"^https?://([^/]+).*$", r"\1", st.get("url") or "")
    body = st.get("body") or ""
    if any(p.lower() in body.lower() for p in COMMON["challenge_phrases"]) and not st.get("hasInput"):
        return "challenge"
    if host in cfg["login_hosts"]:
        return "login_required"
    if not st.get("hasInput") and any(p.lower() in body.lower() for p in cfg["login_phrases"]):
        return "login_required"
    return None


def ask(engine, question, session, state=None, profile=None, mock=None, shot=None,
        answer_timeout=240, settle_polls=3, poll_s=2.0):
    cfg = ENGINES[engine]
    url = cfg["url"]
    if mock:  # e.g. http://127.0.0.1:8766 or http://127.0.0.1:8766?wall=login
        base, _, extra = mock.partition("?")
        url = f"{base.rstrip('/')}/mock_engine.html?engine={engine}" + (f"&{extra}" if extra else "")
    result = {
        "engine": engine, "engine_name": cfg["name"], "engine_url": cfg["url"], "question": question,
        "status": "error", "answer": "", "sources": [], "error": None, "final_url": None,
        "logged_in": bool(state or profile), "mock": bool(mock),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    t0 = time.time()
    b = Browser(session, state=state, profile=profile)

    def finish(status, error=None):
        result["status"] = status
        result["error"] = error
        if shot:
            Path(shot).parent.mkdir(parents=True, exist_ok=True)
            if b.run("screenshot", shot, timeout=30).get("success"):
                result["screenshot"] = shot
        result["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        result["duration_s"] = round(time.time() - t0, 1)
        return result

    r = b.run("open", url, timeout=90)
    if not r.get("success"):
        err = r.get("error") or "open failed"
        return finish("blocked_network" if any(e in err for e in NETWORK_ERRORS) else "error", err)

    # Let the SPA boot, clear cookie banners / "stay logged out" nags, find the prompt box.
    sel = None
    for _ in range(15):
        b.eval(js_dismiss(cfg["dismiss"]))
        sel = b.eval(js_first_visible(cfg["input"]))
        if sel:
            break
        st = b.eval(js_state(cfg)) or {}
        blocked = classify_page(cfg, st)
        if blocked:
            result["final_url"] = st.get("url")
            return finish(blocked, f"page title: {st.get('title')!r}")
        time.sleep(poll_s)
    if not sel:
        st = b.eval(js_state(cfg)) or {}
        result["final_url"] = st.get("url")
        return finish(classify_page(cfg, st) or "no_input", f"no prompt box; title={st.get('title')!r}")

    before_links = {l["href"] for l in (b.eval(js_external_links(cfg["own_hosts"])) or [])}
    before = b.eval(js_state(cfg)) or {}

    # Type the question. contenteditable editors (ProseMirror / Quill / Lexical) need real input events.
    b.eval(js_dismiss(cfg["dismiss"]))
    if not b.run("click", sel).get("success"):
        b.run("focus", sel)
    b.run("keyboard", "inserttext", question)
    probe = question[:24]
    if not b.eval(js_input_has(sel, probe)):
        b.run("fill", sel, question)
    if not b.eval(js_input_has(sel, probe)):
        b.run("keyboard", "type", question, timeout=120)
    time.sleep(0.8)

    sub = b.eval(js_first_visible(cfg["submit"]))
    if not (sub and b.run("click", sub).get("success")):
        b.run("press", "Enter")

    # Wait for a new answer to appear and stop changing.
    deadline = time.time() + answer_timeout
    last_text, stable, st = None, 0, {}
    while time.time() < deadline:
        time.sleep(poll_s)
        b.eval(js_dismiss(cfg["dismiss"]))
        st = b.eval(js_state(cfg)) or {}
        if st.get("count", 0) <= before.get("count", 0) or not st.get("text"):
            blocked = classify_page(cfg, st)
            if blocked:
                result["final_url"] = st.get("url")
                return finish(blocked, f"after submit; title={st.get('title')!r}")
            continue
        if st["text"] == last_text and not st.get("busy"):
            stable += 1
            if stable >= settle_polls:
                break
        else:
            stable, last_text = 0, st["text"]
    result["final_url"] = st.get("url")
    if not last_text:
        return finish("timeout", "no answer text appeared")
    result["answer"] = last_text
    links = b.eval(js_external_links(cfg["own_hosts"])) or []
    result["sources"] = [l for l in links if l["href"] not in before_links]
    return finish("ok" if stable >= settle_polls else "timeout",
                  None if stable >= settle_polls else "answer still streaming at deadline (partial text kept)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", required=True, choices=sorted(ENGINES))
    ap.add_argument("--question", required=True)
    ap.add_argument("--session", default=None, help="agent-browser session name (isolated browser)")
    ap.add_argument("--state", default=None, help="agent-browser auth state JSON exported from YOUR logged-in browser")
    ap.add_argument("--profile", default=None, help="persistent Chrome profile dir")
    ap.add_argument("--mock", default=None, help="base URL serving mocks/ (offline self-test)")
    ap.add_argument("--screenshot", default=None)
    ap.add_argument("--keep-open", action="store_true")
    a = ap.parse_args()
    session = a.session or f"aeo-{a.engine}"
    try:
        res = ask(a.engine, a.question, session, a.state, a.profile, a.mock, a.screenshot)
    finally:
        if not a.keep_open:
            Browser(session).close()
    json.dump(res, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0 if res["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
