# Running Kev and Laya decision models locally with Ollaya

A practical guide to installing [Ollaya](https://github.com/ollaya-dev/ollaya), loading the
[Kev](https://github.com/jaredpalmer/kev) and [Laya](https://github.com/NandhaKishorM/laya) decision
models, and querying them from the command line and over HTTP, on **Windows, macOS and Linux**.

> Tested with Ollaya **0.12.0** on Windows 11 (Intel Core Ultra 9 285HX, 64 GB RAM, NVIDIA RTX PRO
> 4000 Blackwell 16 GB). Every command and response shape shown below was run against that install.

---

## Contents

1. [What these pieces are](#1-what-these-pieces-are)
2. [Requirements](#2-requirements)
3. [Install Ollaya](#3-install-ollaya)
4. [Start and stop the server](#4-start-and-stop-the-server)
5. [Download the models](#5-download-the-models)
6. [Query from the command line](#6-query-from-the-command-line)
7. [Query over HTTP](#7-query-over-http)
8. [Kev vs. Laya: which to use when](#8-kev-vs-laya-which-to-use-when)
9. [Configuration](#9-configuration)
10. [Exposing the server on a network](#10-exposing-the-server-on-a-network)
11. [Recipes: Telegram spam and trading news](#11-recipes-telegram-spam-and-trading-news)
12. [Managing, updating, uninstalling](#12-managing-updating-uninstalling)
13. [Troubleshooting](#13-troubleshooting)
14. [Appendix: Kev's own server](#14-appendix-kevs-own-server)

---

## 1. What these pieces are

**Decision models** don't generate text. You give them a *state* (a message, email, news headline,
JSON object…) and a set of *typed questions*. They answer every question in one pass with
calibrated probabilities, in milliseconds.

| Piece | What it is |
|---|---|
| **Ollaya** | A local server for decision models, "Ollama for decision models". One binary: downloads models, runs them on CPU or GPU, serves an HTTP API on port `11435`. Apache-2.0. |
| **Laya** | Small encoder models (ModernBERT, 322M–421M parameters). Very fast, runs well on CPU. English model has a 512-token context; multilingual model covers 100+ languages. Apache-2.0. |
| **Kev** | Larger decoder models built on Qwen3.5 (0.8B / 4B / 9B in Ollaya). More accurate, especially on questions that need world knowledge; long context (up to 65k tokens). Apache-2.0. |

**Three question types:**

| Type | Asks | Answer |
|---|---|---|
| `choice` | Pick one of several labels | `choice`, `confidence`, `probabilities` per label |
| `score` | Rate on an ordered scale (2–10 levels) | `score` (expected level, e.g. `2.53`), `confidence`, `legend`, `probabilities` per level |
| `noul` | Is this statement true? | `noul`: probability (0–1) that the statement holds |

---

## 2. Requirements

| | Windows | macOS | Linux |
|---|---|---|---|
| OS | Windows 10/11 x64 | **Apple silicon only** (M1 or later) | x86_64 or arm64, **glibc ≥ 2.38** (e.g. Ubuntu 24.04+, Debian 13+) |
| GPU (optional) | NVIDIA, driver R527+ (R580+ for the CUDA 13 pack) | Metal, built in | NVIDIA via CUDA, or CPU only |
| Disk | ~1 GB for Ollaya + GPU pack ~2 GB + models | same, no GPU pack | same |

**Model sizes and memory**

| Model | Download | RAM / VRAM needed (approx.) | Notes |
|---|---|---|---|
| `laya:en` | 853 MB | ~1.8 GB steady, ~3.1 GB peak (measured) | English, 512 tokens |
| `laya:multilingual` | ~600 MB | ~1.5–2.5 GB | 100+ languages, 1,024 tokens by default |
| `laya` | both of the above | sum of both if both get used | Router: picks English or multilingual per request |
| `kev:0.8b` | smaller | ~2–3 GB | Weakest Kev, fine for experiments |
| `kev` (= 4B) | 4.96 GB | ~6–8 GB | Default Kev |
| `kev:9b` | larger | ~10–12 GB | Most accurate Kev that Ollaya ships |

**Rule of thumb for a CPU-only server:** 8 GB RAM is comfortable for Laya; 16 GB if you also want Kev
4B. CPU cores matter more than RAM for speed: plan on 4+ modern x86 cores.

---

## 3. Install Ollaya

### Windows

```powershell
irm https://ollaya.dev/install.ps1 | iex
```

What it does (the script is short and worth reading first: `irm https://ollaya.dev/install.ps1`):

- downloads `ollaya-windows-amd64.zip` from the project's GitHub releases and checks its SHA256
- installs to `%LOCALAPPDATA%\Programs\Ollaya` and adds `...\Ollaya\bin` to your **user** PATH
- if it finds an NVIDIA GPU, downloads the CUDA pack (~1.4 GB) into `lib\ollaya\cuda_v13`
- no services, scheduled tasks, registry or startup entries

Open a **new** terminal afterwards so the PATH change applies.

<details>
<summary><b>Manual install</b> (if <code>irm | iex</code> is blocked, or on a slow/VPN connection)</summary>

```powershell
$base = 'https://github.com/ollaya-dev/ollaya/releases/latest/download'
$dl   = "$env:TEMP\ollaya-dl"; New-Item -ItemType Directory -Force $dl | Out-Null
$dest = "$env:LOCALAPPDATA\Programs\Ollaya"

# 1. Download with resume support (curl.exe ships with Windows 10/11)
curl.exe -L -C - --retry 10 --retry-all-errors -o "$dl\sha256sum.txt"                 "$base/sha256sum.txt"
curl.exe -L -C - --retry 10 --retry-all-errors -o "$dl\ollaya-windows-amd64.zip"      "$base/ollaya-windows-amd64.zip"
curl.exe -L -C - --retry 10 --retry-all-errors -o "$dl\ollaya-windows-amd64-cuda.zip" "$base/ollaya-windows-amd64-cuda.zip"   # NVIDIA only

# 2. Verify checksums
foreach ($f in 'ollaya-windows-amd64.zip','ollaya-windows-amd64-cuda.zip') {
  if (-not (Test-Path "$dl\$f")) { continue }
  $want = (Select-String -Path "$dl\sha256sum.txt" -Pattern ([regex]::Escape($f))).Line.Split(' ')[0]
  $got  = (Get-FileHash -Algorithm SHA256 "$dl\$f").Hash
  if ($got -ne $want) { throw "checksum mismatch: $f" } else { "$f OK" }
}

# 3. Unpack
Expand-Archive "$dl\ollaya-windows-amd64.zip" $dest -Force
if (Test-Path "$dl\ollaya-windows-amd64-cuda.zip") { Expand-Archive "$dl\ollaya-windows-amd64-cuda.zip" $dest -Force }

# 4. Add to user PATH
$bin = "$dest\bin"; $p = [Environment]::GetEnvironmentVariable('Path','User')
if (-not ($p -split ';' -contains $bin)) { [Environment]::SetEnvironmentVariable('Path', "$p;$bin", 'User') }
```

Use `ollaya-windows-amd64-cuda12.zip` instead if your NVIDIA driver is older than R580, or for
Pascal/Volta cards (compute capability < 7.5).
</details>

### macOS (Apple silicon)

```bash
curl -fsSL https://ollaya.dev/install.sh | sh
```

Metal acceleration is built in; there is no separate GPU pack.

### Linux

```bash
curl -fsSL https://ollaya.dev/install.sh | sh
```

To review the script first: `curl -fsSL https://ollaya.dev/install.sh -o install.sh && less install.sh && sh install.sh`.

### Docker (any OS with Docker; ideal for servers)

```bash
# CPU only
docker run -d --name ollaya -p 11435:11435 -v ollaya:/root/.ollaya ghcr.io/ollaya-dev/ollaya

# NVIDIA GPU, driver R580+
docker run -d --name ollaya --gpus=all -p 11435:11435 -v ollaya:/root/.ollaya ghcr.io/ollaya-dev/ollaya:cuda

# NVIDIA GPU, older driver
docker run -d --name ollaya --gpus=all -p 11435:11435 -v ollaya:/root/.ollaya ghcr.io/ollaya-dev/ollaya:cuda12
```

The volume keeps downloaded models across container restarts. Run CLI commands inside the
container with `docker exec -it ollaya ollaya <command>`.

> The volume path `/root/.ollaya` assumes the image runs as root and uses the default model
> directory. If models disappear after a restart, check `docker exec ollaya ollaya show <model>`
> or set `-e OLLAYA_MODELS=/models -v ollaya:/models` explicitly.

### Desktop app

There's also a desktop app for Windows, macOS and Linux (server control and model management in a
GUI) at <https://ollaya.dev/download>.

### Verify

```bash
ollaya --version
```

---

## 4. Start and stop the server

The CLI talks to a background server. Start it once; it listens on `127.0.0.1:11435`.

### Foreground (all OSes)

```bash
ollaya serve
```

Leave that terminal open. You should see:

```
INFO ollaya_server::http: Ollaya is running address=127.0.0.1:11435, [::1]:11435 version="0.12.0" models=...\.ollaya\models
```

Stop it with `Ctrl+C`, or from another terminal with:

```bash
ollaya stop
```

### Background

**Windows (PowerShell):**

```powershell
Start-Process ollaya -ArgumentList serve -WindowStyle Hidden
```

To start it automatically at login, create a scheduled task:

```powershell
$a = New-ScheduledTaskAction -Execute "$env:LOCALAPPDATA\Programs\Ollaya\bin\ollaya.exe" -Argument serve
$t = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
Register-ScheduledTask -TaskName Ollaya -Action $a -Trigger $t -Settings (New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0)
```

**macOS / Linux (quick):**

```bash
nohup ollaya serve > ~/ollaya.log 2>&1 &
```

**Linux as a systemd service (recommended on servers):**

```bash
sudo useradd --system --create-home --home-dir /var/lib/ollaya ollaya
sudo tee /etc/systemd/system/ollaya.service > /dev/null <<EOF
[Unit]
Description=Ollaya decision model server
After=network-online.target

[Service]
User=ollaya
ExecStart=$(command -v ollaya) serve
Environment=OLLAYA_HOST=127.0.0.1:11435
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now ollaya
journalctl -u ollaya -f      # logs
```

Models are stored in the service user's `~/.ollaya/models` (here `/var/lib/ollaya/.ollaya/models`).
Pull models as that user: `sudo -u ollaya ollaya pull laya`.

### Check it's running

```bash
curl http://localhost:11435/api/version
```

---

## 5. Download the models

```bash
ollaya pull laya:en            # Laya English only (853 MB), the quickest start
ollaya pull laya               # Laya router: English + multilingual
ollaya pull kev                # Kev 4B (4.96 GB)
ollaya pull kev:0.8b           # small Kev
ollaya pull kev:9b             # large Kev
```

Downloads come from Hugging Face. Interrupted pulls **resume**: just run the same command again.

| Command | Shows |
|---|---|
| `ollaya list` | Downloaded models and sizes |
| `ollaya show laya:en` | Architecture, parameters, context length, license |
| `ollaya show laya:en --questions` | The model's built-in questions, if any |
| `ollaya ps` | Models currently loaded, and on which device (`cpu`, `cuda:0`, …) |

Example `ollaya ps` on a machine with the CUDA pack:

```
NAME      ID             SIZE     DEVICE   PRECISION   UNTIL
laya:en   c305a9276531   853 MB   cuda:0   F16         4 minutes from now
```

Models load on first use (Laya: 4–15 s, Kev: longer) and unload after 5 minutes idle
(`OLLAYA_KEEP_ALIVE`). Pre-load one so the first real request is fast:

```bash
curl -s http://localhost:11435/api/decide -d '{"model":"kev","keep_alive":"1h"}'
```

---

## 6. Query from the command line

### With a built-in preset

Presets are ready-made question sets:

| Preset | Questions |
|---|---|
| `triage` | intent, is_urgent, frustration, refund_requested, churn_risk |
| `email` | category, is_spam, is_phishing, urgency, needs_reply |
| `guard` | jailbreak, prompt_injection, sensitive_data, harm_severity, topic |
| `moderation` | toxic, harassment, threat, spam, severity |
| `router` | difficulty, domain, needs_tools, is_sensitive |
| `agent` | action, on_task, risk, destructive |

```bash
ollaya run laya:en --preset moderation "JOIN NOW!!! 100x crypto signals, only 20 spots left t.me/vip"
```

```
toxic       no                                    ████████████████ 1.00
harassment  no                                    ████████████████ 1.00
threat      no                                    ███████████████░ 0.94
spam        yes                                   ████████████████ 1.00
severity    1.14 / 3  mild: rude tone or off-to…  ███░░░░░░░░░░░░░ 0.18
```

Swap `laya:en` for `kev` to ask Kev the same questions.

### With your own questions

Put them in a file, e.g. `spam.json`:

```json
{
  "verdict": {
    "type": "choice",
    "instructions": "Is this Telegram message spam?",
    "criteria": {
      "spam": "Unsolicited, scam, phishing, pump or promotional message",
      "legit": "Normal conversation or genuine information"
    }
  }
}
```

```bash
ollaya run kev --questions spam.json "Are we still meeting at 6?"
ollaya run kev --questions spam.json --format json "Are we still meeting at 6?"   # raw JSON
ollaya run kev --questions spam.json --verbose "Are we still meeting at 6?"       # all probabilities + timings
```

Inline JSON works too (starts with `{`). On macOS/Linux:

```bash
ollaya run laya:en --questions '{"spam":{"type":"noul","instructions":"This message is spam."}}' "Are we still meeting at 6?"
```

On Windows, PowerShell mangles inline JSON quotes; use a file instead.

### Other input forms

```bash
cat message.txt | ollaya run laya:en --preset email     # state from stdin (macOS/Linux)
Get-Content message.txt | ollaya run laya:en --preset email   # PowerShell
ollaya run laya:en --preset email                         # no state: interactive REPL
ollaya run kev --state-json '{"from":"x","text":"..."}' --questions q.json   # JSON state
```

---

## 7. Query over HTTP

Base URL: `http://localhost:11435`

| Method & path | Purpose |
|---|---|
| `POST /api/decide` | **Native API.** Answers plus routing info and timings |
| `POST /v1/systemone` | TypeSafe-compatible ("System One") API; `/v1/decisions` is an exact alias |
| `GET /v1/models` | Models, TypeSafe format |
| `GET /api/tags` | Downloaded models |
| `GET /api/ps` | Loaded models and their device |
| `GET /api/version` | Server version |

### Request body

```json
{
  "model": "kev",
  "state": "Exchange halts all withdrawals after a $400M hack. Users panic on social media.",
  "questions": {
    "impact": {
      "type": "choice",
      "instructions": "Price impact on the exchange token?",
      "criteria": { "bullish": "Likely up", "bearish": "Likely down", "neutral": "No clear impact" }
    },
    "severity": {
      "type": "score",
      "instructions": "How severe is this event for holders?",
      "criteria": ["No impact", "Minor", "Serious", "Catastrophic"]
    },
    "is_security": {
      "type": "noul",
      "instructions": "The message reports a security incident."
    }
  }
}
```

| Field | Notes |
|---|---|
| `model` | Required. `laya`, `laya:en`, `laya:multilingual`, `kev`, `kev:9b`, … |
| `state` | String, JSON object or array. Omit it to just load/unload a model |
| `questions` | 1–256 questions, keyed by your own IDs |
| `preset` | Use a built-in or custom preset instead of `questions` |
| `keep_alive` | e.g. `"10m"`, `"1h"`, `0` (unload now), `-1` (keep forever) |

`choice.criteria` can also be a plain list: `["bullish","bearish","neutral"]`. `score.criteria`
lists the levels, lowest first (2–10 levels). For `noul`, the statement goes in `instructions`.

### Response (`/api/decide`)

Real response from `laya:en` to the request above:

```json
{
  "model": "laya:en",
  "answers": {
    "impact":      { "type": "choice", "choice": "neutral", "confidence": 0.3174,
                     "probabilities": { "bullish": 0.0467, "bearish": 0.4084, "neutral": 0.5449 } },
    "severity":    { "type": "score", "score": 2.5285, "confidence": 0.4512,
                     "legend": { "0": "No impact", "1": "Minor", "2": "Serious", "3": "Catastrophic" },
                     "probabilities": { "0": 0.0031, "1": 0.0537, "2": 0.3549, "3": 0.5884 } },
    "is_security": { "type": "noul", "noul": 0.902 }
  },
  "usage": { "input_tokens": 163, "output_tokens": 0 },
  "routing": null,
  "state_truncated": false,
  "done_reason": "decide",
  "total_duration": 7514304700,
  "load_duration": 7467791200,
  "eval_duration": 27510800
}
```

Durations are in **nanoseconds**: here 7.5 s total, of which 7.47 s was the one-time model load and
27 ms the actual answer. `state_truncated: true` means the input was longer than the model's context
and the end was cut off; use Kev for long inputs. `/v1/systemone` returns the same `model`,
`answers` and `usage`, without the routing/timing fields.

Notice that Laya called a $400M exchange hack "neutral" (bearish was a close second). That's the
kind of world-knowledge question where Kev should do better. See [section 8](#8-kev-vs-laya-which-to-use-when).

### curl (macOS / Linux)

```bash
curl -s http://localhost:11435/api/decide \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kev",
    "state": "CONGRATS! You won 1000 USDT. Claim now at t.me/free_usdt_bot",
    "questions": {
      "verdict": { "type": "choice", "instructions": "Is this Telegram message spam?",
                   "criteria": { "spam": "Scam, phishing or promo", "legit": "Normal message" } }
    }
  }'
```

### PowerShell (Windows)

```powershell
$body = @{
  model     = 'kev'
  state     = 'CONGRATS! You won 1000 USDT. Claim now at t.me/free_usdt_bot'
  questions = @{
    verdict = @{
      type         = 'choice'
      instructions = 'Is this Telegram message spam?'
      criteria     = @{ spam = 'Scam, phishing or promo'; legit = 'Normal message' }
    }
  }
} | ConvertTo-Json -Depth 10

$r = Invoke-RestMethod http://localhost:11435/api/decide -Method Post -ContentType 'application/json' -Body $body
$r.answers.verdict
```

### Python (any OS)

```python
import requests  # pip install requests

def decide(model, state, questions, url="http://localhost:11435"):
    r = requests.post(f"{url}/api/decide",
                      json={"model": model, "state": state, "questions": questions},
                      timeout=120)
    r.raise_for_status()
    return r.json()["answers"]

questions = {
    "verdict": {"type": "choice", "instructions": "Is this Telegram message spam?",
                "criteria": {"spam": "Scam, phishing or promo", "legit": "Normal message"}},
    "is_phishing": {"type": "noul", "instructions": "The message tries to steal credentials or crypto."},
}

for model in ("laya:en", "kev"):
    a = decide(model, "Hi dear, your wallet is suspended, send your seed phrase to verify.", questions)
    print(model, a["verdict"]["choice"], a["verdict"]["probabilities"], "phishing:", a["is_phishing"]["noul"])
```

### TypeSafe SDK

Ollaya is wire-compatible with TypeSafe's hosted System One API, so the official TypeSafe SDK works
unchanged when pointed at your local server:

```bash
export TYPESAFE_BASE_URL=http://localhost:11435        # macOS / Linux
$env:TYPESAFE_BASE_URL = 'http://localhost:11435'      # Windows PowerShell
```

---

## 8. Kev vs. Laya: which to use when

| | Laya (`laya:en`) | Kev (`kev`, 4B) |
|---|---|---|
| Speed, NVIDIA GPU | **~12 ms** per question (measured) | ~0.1–0.9 s per request (Ollaya's published figures) |
| Speed, CPU only | **~70 ms** short message, ~0.5 s at 512 tokens (measured) | ~1.3–25 s per request (Ollaya's published figures) |
| Memory | ~2–3 GB | ~6–8 GB |
| Context | 512 tokens (en), 1,024+ (multilingual) | up to 65k tokens |
| Languages | English, or 100+ with `laya`/`laya:multilingual` | Multilingual (Qwen base) |
| Strengths | Spam, moderation, routing, triage, high volume, CPU servers | Questions needing world knowledge or reasoning, long documents, nuanced judgement |
| Accuracy (Kev authors' held-out sets) | n/a | 4B: 0.817 / 9B: 0.820 (new sources); hosted Jev: 0.857 |

**Results on a small hand-made test set** (8 Telegram messages, 6 market headlines; a sanity check,
not a benchmark):

| | Spam (8) | News sentiment (6) |
|---|---|---|
| `laya:en` | **8/8** | 4/6: called "SEC approves ETH ETFs" and "Tesla recalls 2M vehicles" neutral |
| `kev` | _to be filled in_ | _to be filled in_ |

**Practical pattern:** use Laya as the fast first pass on everything, and send only uncertain cases
(e.g. top probability < 0.7) or knowledge-heavy questions to Kev.

---

## 9. Configuration

Set these before `ollaya serve`:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAYA_HOST` | `127.0.0.1:11435` | Bind address (server) / target (CLI) |
| `OLLAYA_MODELS` | `~/.ollaya/models` | Where models are stored |
| `OLLAYA_KEEP_ALIVE` | `5m` | How long a model stays loaded after its last request |
| `OLLAYA_DEVICE` | `auto` | Compute device for model runners (`auto` picks the GPU if usable) |
| `OLLAYA_API_KEY` | unset | Require `Authorization: Bearer <key>` on every request |
| `OLLAYA_THREADS` | unset | CPU threads per model |
| `OLLAYA_MAX_LOADED_MODELS` | `3` | How many models may be loaded at once |

How to set them:

```powershell
# Windows, current terminal only
$env:OLLAYA_KEEP_ALIVE = '1h'; ollaya serve
# Windows, permanently for your user (new terminals)
[Environment]::SetEnvironmentVariable('OLLAYA_KEEP_ALIVE', '1h', 'User')
```

```bash
# macOS / Linux, one run
OLLAYA_KEEP_ALIVE=1h ollaya serve
# permanently: add `export OLLAYA_KEEP_ALIVE=1h` to ~/.bashrc or ~/.zshrc
# systemd: add `Environment=OLLAYA_KEEP_ALIVE=1h` under [Service], then `sudo systemctl restart ollaya`
```

---

## 10. Exposing the server on a network

By default the server only listens on localhost. To reach it from other machines:

```bash
OLLAYA_HOST=0.0.0.0:11435 OLLAYA_API_KEY='change-me-long-random' ollaya serve
```

Then every request needs the key:

```bash
curl -s http://SERVER:11435/api/decide -H "Authorization: Bearer change-me-long-random" -H "Content-Type: application/json" -d '{...}'
```

The CLI and SDKs send `OLLAYA_API_KEY` automatically when it's set in their environment.

Recommendations:

- **Always** set `OLLAYA_API_KEY` when binding to `0.0.0.0`.
- Restrict the port with the firewall (`sudo ufw allow from <your-ip> to any port 11435` on Ubuntu;
  Windows Defender Firewall inbound rule on Windows).
- For access over the internet, put it behind a reverse proxy with TLS (Caddy, nginx), or keep it on
  a private network such as Tailscale/WireGuard rather than opening the port publicly.

---

## 11. Recipes: Telegram spam and trading news

### Telegram spam filter

```python
import requests

SPAM_Q = {
    "verdict": {"type": "choice", "instructions": "Is this Telegram message spam?",
                "criteria": {"spam": "Unsolicited, scam, phishing, pump or promotional message",
                             "legit": "Normal conversation or genuine information"}},
    "is_phishing": {"type": "noul", "instructions": "The message tries to obtain passwords, seed phrases or money."},
}

def is_spam(text, threshold=0.8):
    a = requests.post("http://localhost:11435/api/decide",
                      json={"model": "laya", "state": text, "questions": SPAM_Q}).json()["answers"]
    p_spam = a["verdict"]["probabilities"]["spam"]
    if 0.3 < p_spam < threshold:  # unsure: ask the bigger model
        a = requests.post("http://localhost:11435/api/decide",
                          json={"model": "kev", "state": text, "questions": SPAM_Q}).json()["answers"]
        p_spam = a["verdict"]["probabilities"]["spam"]
    return p_spam >= threshold or a["is_phishing"]["noul"] >= 0.9, p_spam
```

Using `laya` (the router) instead of `laya:en` handles German and other languages automatically.

### Trading news sentiment

```python
NEWS_Q = {
    "direction": {"type": "choice", "instructions": "What does this news imply for the price of the asset it is about?",
                  "criteria": {"bullish": "Likely to push the price up",
                               "bearish": "Likely to push the price down",
                               "neutral": "No clear price impact"}},
    "magnitude": {"type": "score", "instructions": "How large is the likely price move?",
                  "criteria": ["Negligible", "Small", "Large", "Extreme"]},
    "is_rumor": {"type": "noul", "instructions": "The news is unconfirmed rumor or speculation."},
}
```

> ⚠️ These models judge **text**, not prices. They can tell you whether a headline reads bullish or
> bearish; they cannot forecast price from charts or OHLC data. Treat the output as one signal inside
> your own rules, backtest it, and never let it place trades unsupervised.

### Ready-made comparison script

[`compare.py`](compare.py) (Python standard library only, no installs needed) runs a labelled spam +
sentiment test set against any models and prints accuracy and latency:

```bash
python compare.py laya:en kev
python compare.py --url http://SERVER:11435 laya
```

On Windows, run `$env:PYTHONIOENCODING = 'utf-8'` first so the ✓/✗ marks print correctly.

---

## 12. Managing, updating, uninstalling

```bash
ollaya ps                 # what's loaded, on which device
ollaya stop kev           # unload one model
ollaya stop               # stop the server (unloads everything)
ollaya rm kev:0.8b        # delete a downloaded model
ollaya update --check     # is there a newer Ollaya?
ollaya update             # install it
ollaya preset list        # presets; `ollaya preset create` for your own
ollaya mcp                # expose models to AI agents (e.g. Claude) over MCP
```

**Uninstall**

| OS | Remove |
|---|---|
| Windows | `ollaya stop`, delete `%LOCALAPPDATA%\Programs\Ollaya` and `%USERPROFILE%\.ollaya`, remove `...\Ollaya\bin` from your user PATH (Settings → System → About → Advanced system settings → Environment Variables) |
| macOS / Linux | `ollaya stop`, `rm "$(command -v ollaya)"`, `rm -rf ~/.ollaya`; on systemd: `sudo systemctl disable --now ollaya && sudo rm /etc/systemd/system/ollaya.service` |
| Docker | `docker rm -f ollaya && docker volume rm ollaya` |

---

## 13. Troubleshooting

| Problem | Fix |
|---|---|
| `could not connect to a running Ollaya instance` | Start the server: `ollaya serve` |
| Downloads crawl or drop (corporate VPN/proxy) | `ollaya pull` resumes: re-run it, or loop: `until ollaya pull kev; do sleep 5; done`. For the Windows GPU pack use the manual install with `curl -C -`. Fastest fix: download off-VPN |
| `ollaya ps` shows `cpu` despite an NVIDIA GPU | The CUDA pack is missing: check for `%LOCALAPPDATA%\Programs\Ollaya\lib\ollaya\cuda_v13` (Windows), re-run the installer, then restart `ollaya serve`. Check `nvidia-smi` works |
| First request takes seconds | That's the model loading (Laya ~4–15 s, Kev longer). Pre-load with `keep_alive` (section 5) or raise `OLLAYA_KEEP_ALIVE` |
| `state_truncated: true` | Input exceeded the model's context (Laya English: 512 tokens). Use `laya:multilingual` (1,024), Kev (65k), or split the text |
| Inline `--questions '{...}'` fails on Windows | PowerShell strips the quotes; put the questions in a file |
| Out of memory with several models | Lower `OLLAYA_MAX_LOADED_MODELS`, or unload with `ollaya stop <model>` |
| Linux binary won't start (`GLIBC_2.38 not found`) | The distro is too old: use Ubuntu 24.04+ / Debian 13+, or the Docker image |
| Overconfident probabilities | Laya's checkpoints are known to be overconfident as shipped; tune your thresholds on your own labelled examples |

---

## 14. Appendix: Kev's own server

Kev also ships its own PyTorch server, useful for `kev-27b` (not in Ollaya) or for fine-tuning work.
It needs **CUDA/ROCm or Apple-silicon MLX**: there's no CPU path. In bf16, 4B and 9B need ~17 GB VRAM
and 27B needs an 80 GB GPU.

```bash
git clone https://github.com/jaredpalmer/kev.git && cd kev
uv sync --extra serve
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-4b --port 8009
# POST http://localhost:8009/v1/systemone  (same request format as above)
```

For a 16 GB GPU or a CPU server, Ollaya's GGUF builds of Kev are the practical route.

---

*Sources: [Ollaya](https://github.com/ollaya-dev/ollaya) · [Ollaya API docs](https://github.com/ollaya-dev/ollaya/blob/main/docs/api.md) · [Kev](https://github.com/jaredpalmer/kev) · [Laya](https://github.com/NandhaKishorM/laya)*
