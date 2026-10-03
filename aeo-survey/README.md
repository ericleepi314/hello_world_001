# Clawcodex AEO survey

This survey checks how answer engines (ChatGPT, Gemini, Perplexity) respond to:

> What are the competitive advantages of Clawcodex compared to other Python-based coding agents?

It asks 12 variants of that question, written from four angles, and saves every
answer next to its question.

## Team layout

```
orchestrator (main session)
 ├─ sub-agent A  direct comparison      ─┐  each one runs in its own git worktree
 ├─ sub-agent B  recommendation / buyer  ├─ with its own agent-browser sessions
 ├─ sub-agent C  feature-specific claims │  (aeo-<agent>-chatgpt|gemini|perplexity)
 └─ sub-agent D  evaluation / skeptic   ─┘
        │ each one: 3 variants × 3 engines → results/raw/<agent>.jsonl
        ▼
 collect.py → results/answers.md + results/answers.json
```

| File | Purpose |
| --- | --- |
| `questions.json` | Base question, plus 3 variants for each sub-agent (B3 is unbranded, to see whether Clawcodex comes up on its own) |
| `engines.json` | Each engine's URL and CSS selectors: composer, send, stop, answer, and the cookie / "stay logged out" pop-ups |
| `ask_engine.py` | Sends one question to one engine through agent-browser and returns the answer, its sources, and a status |
| `run_batch.py` | Runs one sub-agent's variants against every engine. Each run is isolated, and re-runs skip pairs already answered |
| `collect.py` | Merges all raw results into `results/answers.{md,json}` and adds a scorecard: does the answer recognise Clawcodex, and which competitors does it name? |
| `SUBAGENT_PROMPT.md` | The brief each sub-agent is launched with |
| `mocks/mock_engine.html` | Offline copy of the three engines' DOMs, used to self-test the harness (`--mock`) |

## Running it

```bash
npm i -g agent-browser          # Chromium already lives at /opt/pw-browsers/chromium
cd aeo-survey

# offline self-test (no network needed)
python3 -m http.server 8766 --directory mocks &
python3 run_batch.py --agent A --mock http://127.0.0.1:8766 && python3 collect.py --mock

# real survey: one sub-agent per group, normally launched in parallel by the orchestrator
for g in A B C D; do python3 run_batch.py --agent $g; done
python3 collect.py              # → results/answers.md
```

Each record has one of these statuses:

| Status | Meaning |
| --- | --- |
| `ok` | Answer captured |
| `blocked_network` | The sandbox's egress policy refused the host |
| `login_required` | The site requires sign-in |
| `challenge` | The site showed a CAPTCHA or bot check (never solved automatically) |
| `no_input` | No prompt box was found, so the selectors are probably stale |
| `timeout` | The answer never finished streaming |
| `error` | Anything else; see the `error` field |

## Network access the survey needs

The cloud environment's network policy has to allow these hosts. Choosing "Full"
network access also works.

- ChatGPT: `chatgpt.com`, `*.chatgpt.com`, `*.openai.com`, `*.oaistatic.com`, `*.oaiusercontent.com`
- Gemini: `gemini.google.com`, `accounts.google.com`, `consent.google.com`, `www.google.com`, `*.gstatic.com`, `*.googleapis.com`, `*.googleusercontent.com`
- Perplexity: `www.perplexity.ai`, `perplexity.ai`, `*.perplexity.ai`
- Bot-check widgets: `challenges.cloudflare.com`

## Login

ChatGPT and Perplexity both answer without an account. The harness dismisses
their cookie banners and "stay logged out" nags. Gemini may require a Google
sign-in, depending on region.

The harness never creates accounts, types passwords, or solves CAPTCHAs. To use
your own logged-in session:

1. On your own machine, run `agent-browser --headed open https://gemini.google.com` and log in.
2. Run `agent-browser state save gemini-auth.json`.
3. Make the file available in the sandbox outside git (for example `aeo-survey/auth/`, which is gitignored).
4. Run with `AEO_STATE_GEMINI=/path/gemini-auth.json`.

The same works for `AEO_STATE_CHATGPT` and `AEO_STATE_PERPLEXITY`.

## Note on terms of service

These consumer web apps generally forbid automated access in their terms. The
harness keeps volume small (36 queries) and makes no attempt to get around bot
checks. For recurring tracking, the official APIs are the terms-compliant route:
OpenAI, Gemini, and Perplexity Sonar.
