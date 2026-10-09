# Running Kev and Laya decision models locally with Ollaya

A practical guide to installing [Ollaya](https://github.com/ollaya-dev/ollaya), loading the
[Kev](https://github.com/jaredpalmer/kev) and [Laya](https://github.com/NandhaKishorM/laya) decision
models, and querying them from the command line and over HTTP, on **Windows, macOS and Linux**.

> Tested with Ollaya **0.12.0** on Windows 11 (Intel Core Ultra 9 285HX, 64 GB RAM, NVIDIA RTX PRO
> 4000 Blackwell 16 GB), with `laya:en`, `laya:multilingual`, the `laya` router and `kev` (4B).
>
> **What was verified:** everything on Windows (install, server, CLI, HTTP API, Python, SDK, API key,
> GPU and CPU), plus all response examples, code samples and measurements. **Taken from Ollaya's docs, not run here:** the
> macOS/Linux installer, Docker, systemd, `kev:0.8b`/`kev:9b`, `ollaya mcp`/`update`, and Kev's own
> PyTorch server (appendix). Those are marked *(from docs)* where they appear.

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
| **Kev** | Larger decoder models built on Qwen3.5 (0.8B / 4B / 9B in Ollaya). More accurate, especially on questions that need world knowledge; 8,192-token context in Ollaya (the upstream model goes up to 65k). Officially listed as English (`ollaya show kev`), but it handled German messages well in testing (section 8). Apache-2.0. |

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
| `laya:en` | 853 MB | CPU: ~1.8 GB steady, ~3.1 GB peak · GPU: ~0.9 GB VRAM (measured) | English, 512 tokens |
| `laya:multilingual` | 683 MB | similar to `laya:en` | 100+ languages, 1,024 tokens by default |
| `laya` | both of the above (listed as `laya:latest`, 11 KB, plus the two models) | sum of both if both get used | Router: detects the language and picks English or multilingual per request |
| `kev` (= 4B) | **9.5 GB** | CPU: **~8 GB RAM** · GPU: **~9.5 GB VRAM** (measured) | Default Kev. Ships as ONNX in full precision (F32), 8,192-token context |
| `kev:0.8b`, `kev:9b` | not measured | estimate: roughly ¼× and 2× of `kev` | Smaller / larger Kev *(from docs, not tested)* |

**Rule of thumb for a CPU-only server:** 8 GB RAM for Laya only; **16 GB minimum, 32 GB comfortable**
for Kev 4B plus Laya. CPU cores matter more than RAM for speed: plan on 4+ modern x86 cores (8+ for Kev).

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

### macOS (Apple silicon) *(from docs)*

```bash
curl -fsSL https://ollaya.dev/install.sh | sh
```

Metal acceleration is built in; there is no separate GPU pack.

### Linux *(from docs)*

```bash
curl -fsSL https://ollaya.dev/install.sh | sh
```

To review the script first: `curl -fsSL https://ollaya.dev/install.sh -o install.sh && less install.sh && sh install.sh`.

### Docker (any OS with Docker; ideal for servers) *(from docs)*

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

**Linux as a systemd service (recommended on servers)** *(standard systemd setup, not tested with Ollaya)*:

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
ollaya pull kev                # Kev 4B (9.5 GB)
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

Models load on first use (measured: Laya ~3–7 s, up to ~15 s on the very first GPU load; Kev ~8–10 s,
but ~40 s for the first load after a reboot, while its 9.5 GB file is read from disk) and unload after
5 minutes idle
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

`score.criteria` lists the levels, lowest first (2–10 levels). For `noul`, the statement goes in
`instructions`.

`choice.criteria` is an object of label → description. Laya also accepts a plain list
(`["bullish","bearish","neutral"]`), but **Kev rejects lists** with `INVALID_REQUEST`; for labels
without descriptions use `{"bullish": null, "bearish": null, "neutral": null}`. Descriptions are worth
writing, though: with bare labels Kev was close to a coin-flip on "SEC approves spot Ethereum ETFs"
(bullish 49% vs. neutral 46%), and with descriptions it answered bullish at 89%.

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

Notice that Laya called a $400M exchange hack "neutral" (bearish was a close second). Kev, given the
same request, answered **bearish at 88%**, severity 2.34 / 3 and `is_security` 0.82. World-knowledge
questions like this are where Kev is clearly better; see [section 8](#8-kev-vs-laya-which-to-use-when).

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

### Python SDK (`typesafe-sdk`)

Ollaya has no Python package of its own, but it's wire-compatible with TypeSafe's hosted System One
API, so TypeSafe's official SDK works unchanged against your local server. It gives you typed
responses, retries, timeouts, an async client and proper exceptions. Tested with `typesafe-sdk` 0.7.2:

```bash
pip install typesafe-sdk
```

```python
from typesafe_sdk import TypeSafeClient

# The api_key isn't checked by a local Ollaya unless you set OLLAYA_API_KEY; then pass that key here.
with TypeSafeClient(base_url="http://localhost:11435", api_key="local", model="laya:en") as client:
    r = client.system_one(
        state="Hi dear, your wallet is suspended, send your seed phrase to verify.",
        questions={
            "verdict": {"type": "choice", "instructions": "Is this Telegram message spam?",
                        "criteria": {"spam": "Scam, phishing or promo", "legit": "Normal message"}},
            "is_phishing": {"type": "noul", "instructions": "The message tries to steal credentials or crypto."},
        },
    )
    print(r.answers["verdict"].choice, r.answers["verdict"].probabilities)  # spam {'spam': 0.695, 'legit': 0.305}
    print(r.answers["is_phishing"].noul)                                    # 0.6672

    # Override the model per call, e.g. escalate unsure cases to Kev:
    r2 = client.system_one(state=r_state, questions=r_questions, model="kev")   # your state / questions
```

Instead of constructor arguments you can use environment variables:

```bash
export TYPESAFE_BASE_URL=http://localhost:11435 TYPESAFE_API_KEY=local TYPESAFE_DEFAULT_MODEL=laya   # macOS / Linux
```

```powershell
$env:TYPESAFE_BASE_URL = 'http://localhost:11435'; $env:TYPESAFE_API_KEY = 'local'; $env:TYPESAFE_DEFAULT_MODEL = 'laya'   # Windows
```

For asyncio (e.g. a Telegram bot), use `AsyncTypeSafeClient` with `async with` / `await client.system_one(...)`.

The SDK talks to `/v1/systemone`, so it doesn't expose Ollaya-only extras like routing info,
timings, presets or `keep_alive`. For those, call `/api/decide` directly (see the `requests` example above).

---

## 8. Kev vs. Laya: which to use when

All numbers below were measured on the test machine (24-core Intel Core Ultra 9, RTX PRO 4000 16 GB)
unless noted. Expect CPU times to be several times slower on a small server.

| | Laya (`laya:en`) | Kev (`kev`, 4B) |
|---|---|---|
| Speed, NVIDIA GPU | **~12 ms** per request | **~160–180 ms** per request with free GPU memory; **~4.5 s** when the GPU was nearly full (see below) |
| Speed, CPU only | **~70 ms** short message, ~0.5 s at 512 tokens | **~2.2 s** per request |
| Model load (first request) | ~3–7 s (up to ~15 s on the very first GPU load) | ~8–10 s |
| Memory | CPU ~2–3 GB RAM · GPU ~0.9 GB VRAM | CPU ~8 GB RAM · GPU ~9.5 GB VRAM |
| Context | 512 tokens (en), 1,024+ (multilingual) | 8,192 tokens |
| Strengths | English spam, moderation, routing, triage, high volume, CPU servers | World knowledge, German/other languages, nuanced judgement, longer texts |
| Accuracy (Kev authors' held-out sets) | n/a | 4B: 0.817 / 9B: 0.820 (new sources); hosted Jev: 0.857 |

**Results on a small hand-made test set** (a sanity check, not a benchmark). The English tests used
`laya:en` and are reproducible with [`compare.py`](compare.py); the German test used the `laya` router,
which sent three messages to `laya:multilingual` and one to `laya:en`. Accuracy was identical on GPU and CPU.

| Test | Laya | Kev |
|---|---|---|
| English Telegram spam (8) | **8/8** | **8/8**, with higher confidence on the subtle scams (96% vs. 68–70%) |
| English market-news sentiment (6) | 4/6: called "SEC approves ETH ETFs" and "Tesla recalls 2M vehicles" neutral | **6/6** |
| German Telegram messages (4) | 2/4: **missed both scams** (prize scam, fake crypto support); the router also sent one of them to the English model | **4/4** |

**Practical patterns:**

- **English only, high volume or CPU server:** Laya as the first pass on everything; send only unsure cases
  (e.g. spam probability between 0.2 and 0.8) or knowledge-heavy questions to Kev. See the recipe in section 11.
- **German or mixed-language messages:** use Kev. In these tests the multilingual Laya wasn't reliable
  enough for spam.
- **Market-news sentiment:** use Kev. Laya lacks the world knowledge to know that an ETF approval is bullish.

**Two GPU caveats for Kev:**

- **It needs memory headroom.** Kev 4B plus Laya used ~11.9 GB of the 16 GB card. With another GPU app
  running (LM Studio, holding 4.1 GB; note that it keeps running in the system tray after you close its
  window), the card was full and Kev's median latency rose from ~160 ms to ~4.5 s. Check `nvidia-smi`.
- **On the tested laptop GPU, Kev breaks after pauses of ~15 s or more** between requests, until it's
  reloaded. See [troubleshooting](#kev-fails-on-the-gpu-with-inference_failed) for details and fixes.
  On **CPU, Kev ran without errors** through every test, including long idle periods.

---

## 9. Configuration

Set these before `ollaya serve`:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAYA_HOST` | `127.0.0.1:11435` | Bind address (server) / target (CLI) |
| `OLLAYA_MODELS` | `~/.ollaya/models` | Where models are stored |
| `OLLAYA_KEEP_ALIVE` | `5m` | How long a model stays loaded after its last request |
| `OLLAYA_DEVICE` | `auto` | Compute device for model runners (`auto` picks the GPU if usable; `cpu` forces CPU) |
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

Then every request needs the key; without it (or with a wrong one) the server answers `401`. Only
`GET /` stays open, so health checks work without a key.

```bash
curl -s http://SERVER:11435/api/decide -H "Authorization: Bearer change-me-long-random" -H "Content-Type: application/json" -d '{...}'
```

The `ollaya` CLI sends `OLLAYA_API_KEY` automatically when it's set in its environment. That
includes `ollaya stop`: without the key it can't stop a protected server
(`OLLAYA_API_KEY=... ollaya stop`). The
`typesafe-sdk` client does **not** read `OLLAYA_API_KEY`: pass the key as `api_key=` or set
`TYPESAFE_API_KEY` to the same value.

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

def decide(model, text):
    r = requests.post("http://localhost:11435/api/decide",
                      json={"model": model, "state": text, "questions": SPAM_Q}, timeout=120)
    r.raise_for_status()
    return r.json()

def is_spam(text, threshold=0.8):
    d = decide("laya", text)                      # fast first pass; the router detects the language
    p_spam = d["answers"]["verdict"]["probabilities"]["spam"]
    english = d["model"] == "laya:en"
    if not english or 0.2 < p_spam < threshold:   # non-English or unsure: ask Kev
        d = decide("kev", text)
        p_spam = d["answers"]["verdict"]["probabilities"]["spam"]
    return p_spam >= threshold or d["answers"]["is_phishing"]["noul"] >= 0.9, p_spam
```

If Kev runs on a laptop GPU, swap this `decide()` for the unload-and-retry version in
[troubleshooting](#kev-fails-on-the-gpu-with-inference_failed); Telegram traffic has exactly the kind
of pauses that trigger that issue. On CPU this isn't needed.

Non-English messages always go to Kev, because in testing the multilingual Laya missed German scams.
The router also once classified a German message as English, so **if your chats are mostly German,
skip Laya and send everything to Kev** (~160 ms on a GPU, ~2 s on a fast CPU).

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
ollaya preset list        # built-in and custom presets
ollaya update --check     # is there a newer Ollaya?          (from docs)
ollaya update             # install it                          (from docs)
ollaya mcp                # expose models to AI agents (e.g. Claude) over MCP, stdio (from docs)
ollaya mcp --http         # same over HTTP at 127.0.0.1:11436/mcp                    (from docs)
```

See `ollaya <command> --help` for all options, e.g. `ollaya preset create --help` for your own presets.

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
| First request takes seconds | That's the model loading (Laya ~3–15 s, Kev ~8–10 s). Pre-load with `keep_alive` (section 5) or raise `OLLAYA_KEEP_ALIVE` |
| `state_truncated: true` | Input exceeded the model's context (Laya English: 512 tokens). Use `laya:multilingual` (1,024), Kev (8,192), or split the text |
| Kev on GPU fails with `INFERENCE_FAILED` … `running Scan node` … `UpdateWithParentStream` | See [below](#kev-fails-on-the-gpu-with-inference_failed) |
| Kev on GPU takes seconds instead of ~160 ms | GPU memory is nearly full, so Windows spills to system RAM. Check `nvidia-smi`; quit other GPU apps (e.g. LM Studio, which keeps a model loaded from the system tray after you close its window), or unload Laya |
| Inline `--questions '{...}'` fails on Windows | PowerShell strips the quotes; put the questions in a file |
| Out of memory with several models | Lower `OLLAYA_MAX_LOADED_MODELS`, or unload with `ollaya stop <model>` |
| Linux binary won't start (`GLIBC_2.38 not found`) | The distro is too old: use Ubuntu 24.04+ / Debian 13+, or the Docker image |
| Overconfident probabilities | Laya's checkpoints are known to be overconfident as shipped; tune your thresholds on your own labelled examples |
| `INVALID_REQUEST` … `takes choice criteria as an object` | Kev doesn't accept a list of labels; use `{"label": "description"}` or `{"label": null}` (section 7) |
| `401` / `missing or invalid API key` | The server has `OLLAYA_API_KEY` set: send `Authorization: Bearer <key>`, set `OLLAYA_API_KEY` for the CLI, or pass `api_key=` to the SDK |

### Kev fails on the GPU with `INFERENCE_FAILED`

Observed with Ollaya 0.12.0, Kev 4B on CUDA (RTX PRO 4000, 16 GB, Windows):

```
onnx runtime: Non-zero status code returned while running Scan node. Name:'node_scan__1' ...
UpdateWithParentStream Subgraph has nodes running on device: ... this is not supported yet.
```

- **What happens:** Kev works after loading, but after a **pause of roughly 15 s or more between Kev
  requests**, the next request fails, and every later one too, until Kev is reloaded. Laya keeps working.
- **What the tests showed:**

  | Pattern | Result |
  |---|---|
  | Kev requests back-to-back or every 2 s (59 requests over 3 min) | always OK |
  | Kev every 15–20 s | failed within 16–45 s in every run |
  | A tiny Laya request every 5 s to keep the GPU busy, Kev every 30–60 s | mostly OK, but still failed once |
  | Kev alone on a completely free GPU (10.5 of 16 GB used) | still fails, so it's **not** GPU memory |
  | Kev on CPU (`OLLAYA_DEVICE=cpu`), any pattern including minutes of idle | always OK |

- **Likely cause:** each failure coincided with the laptop GPU having dropped into its deepest idle
  power state (P8 in `nvidia-smi --query-gpu=pstate --format=csv`). It looks like an ONNX Runtime /
  CUDA issue when the GPU wakes up. Seen on a Blackwell laptop GPU (compute capability 12.0, driver
  595.71); desktop and server GPUs may behave differently, but that wasn't tested.
- **Fixes, best first:**
  1. **Run Kev on CPU** if ~2 s per request is acceptable: `OLLAYA_DEVICE=cpu ollaya serve`. It's fully
     reliable, and on a CPU-only server this issue doesn't apply at all.
  2. **Unload and retry in your code** (below). After a pause, that request costs a ~9 s reload, then it's
     fast again while traffic is steady.
  3. Recover by hand with `ollaya stop kev`; Kev reloads on the next request.
  4. *Untested:* NVIDIA Control Panel → Manage 3D settings → Power management mode → "Prefer maximum
     performance" might keep the GPU out of P8.

Unload-and-retry:

```python
import requests
URL = "http://localhost:11435/api/decide"

def decide(model, state, questions, retries=1):
    for attempt in range(retries + 1):
        r = requests.post(URL, json={"model": model, "state": state, "questions": questions}, timeout=300)
        if r.status_code == 200:
            return r.json()
        if attempt < retries and r.json().get("code") == "INFERENCE_FAILED":
            requests.post(URL, json={"model": model, "keep_alive": 0}, timeout=60)  # unload; next call reloads
            continue
        r.raise_for_status()
```

---

## 14. Appendix: Kev's own server

*(From Kev's README, not tested here.)* Kev also ships its own PyTorch server, useful for `kev-27b` (not in Ollaya) or for fine-tuning work.
It needs **CUDA/ROCm or Apple-silicon MLX**: there's no CPU path. In bf16, 4B and 9B need ~17 GB VRAM
and 27B needs an 80 GB GPU.

```bash
git clone https://github.com/jaredpalmer/kev.git && cd kev
uv sync --extra serve
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-4b --port 8009
# POST http://localhost:8009/v1/systemone  (same request format as above)
```

For a 16 GB GPU or a CPU server, Ollaya is the practical route: its Kev 4B ran in ~9.5 GB VRAM on the
test GPU and ~8 GB RAM on CPU.

---

*Sources: [Ollaya](https://github.com/ollaya-dev/ollaya) · [Ollaya API docs](https://github.com/ollaya-dev/ollaya/blob/main/docs/api.md) · [Kev](https://github.com/jaredpalmer/kev) · [Laya](https://github.com/NandhaKishorM/laya)*
