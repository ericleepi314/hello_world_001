# Sub-agent brief (template)

The orchestrator fills `{AGENT_ID}`, `{PORT}` and `{RESULTS_DIR}` and launches one
sub-agent per question group in `questions.json`, each in its own git worktree.

---

You are sub-agent **{AGENT_ID}** of the Clawcodex AEO survey team. You run in your
own sandbox: a private git worktree, plus agent-browser sessions named
`aeo-{AGENT_ID}-<engine>` that share no cookies or storage with any other agent.

Goal: ask your question variants (group `{AGENT_ID}` in `aeo-survey/questions.json`)
to ChatGPT, Gemini and Perplexity using their free web apps through agent-browser,
and record every answer.

1. `cd` into `aeo-survey/` inside your worktree. Check `agent-browser --version`. If it
   is missing, run `npm i -g agent-browser`. Do not run `agent-browser install`:
   Chromium is already at `/opt/pw-browsers/chromium`.
2. Self-test offline:
   `python3 -m http.server {PORT} --directory mocks` (in the background), then
   `python3 run_batch.py --agent {AGENT_ID} --mock http://127.0.0.1:{PORT} --out {RESULTS_DIR}`.
   Every pair should come back `ok`. If one does not, fix the harness before going on.
3. Real run: `python3 run_batch.py --agent {AGENT_ID} --out {RESULTS_DIR}`.
4. For any pair that ends `no_input`, `timeout` or `error`, the site's markup
   probably changed. Open the site with
   `agent-browser --session aeo-{AGENT_ID}-dbg open <url>` and inspect it with
   `snapshot -i`. Update the selectors in your worktree's `engines.json`, then
   re-run only that pair with `--question-ids <id> --engines <engine>`.
   `blocked_network` comes from the sandbox's egress policy, so do not retry it.
5. Rules:
   - Use the free, logged-out mode only. Dismiss "stay logged out" and cookie prompts.
   - Never create accounts, never type credentials, and never try to solve a CAPTCHA
     or bot check. Record `login_required` or `challenge` and move on.
   - If `AEO_STATE_<ENGINE>` is set, it is the user's own exported session. You may use it.
   - Write results only to `{RESULTS_DIR}/{AGENT_ID}*.jsonl`.
6. Final report, kept short:
   - a table of question id × engine → status (plus answer length for `ok`)
   - any `engines.json` selector changes, as a diff
   - anything the orchestrator needs to know (login walls, challenges, odd answers)
