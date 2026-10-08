"""Compare decision models served by a local Ollaya instance on labelled test cases.

Usage:  python compare.py laya:en kev
        python compare.py --url http://myserver:11435 laya:en
"""
import argparse
import json
import urllib.request

SPAM_QUESTION = {
    "type": "choice",
    "instructions": "Is this Telegram message spam?",
    "criteria": {
        "spam": "Unsolicited, scam, phishing, pump or promotional message",
        "legit": "Normal conversation or genuine information",
    },
}

SENTIMENT_QUESTION = {
    "type": "choice",
    "instructions": "What does this news imply for the price of the asset it is about?",
    "criteria": {
        "bullish": "Likely to push the price up",
        "bearish": "Likely to push the price down",
        "neutral": "No clear price impact",
    },
}

# (expected label, text)
SPAM_CASES = [
    ("spam", "CONGRATS! You won 1000 USDT. Claim now at t.me/free_usdt_bot before it expires!"),
    ("spam", "🚀🚀 $PEPE2 launching in 10 min, 100x guaranteed, join our VIP pump group, only 50 spots left"),
    ("spam", "Hi dear, I'm Anna from the crypto support team. Your wallet is suspended, send your seed phrase to verify."),
    ("spam", "Earn $500/day from home with no experience. DM me for details 💰"),
    ("legit", "Hey, are we still meeting at 6 for the project review?"),
    ("legit", "Reminder: the group call is moved to Thursday because of the holiday."),
    ("legit", "Does anyone know if the Binance API rate limit changed this week? My bot keeps getting 429s."),
    ("legit", "I sold half my BTC position today, taking some profit before the Fed meeting."),
]

SENTIMENT_CASES = [
    ("bullish", "Apple beats quarterly earnings expectations and raises full-year guidance."),
    ("bullish", "SEC approves spot Ethereum ETFs; inflows expected to start next week."),
    ("bearish", "Tesla recalls 2 million vehicles and cuts delivery forecast for the year."),
    ("bearish", "Major exchange halts withdrawals after a $400M hack; its token drops in early trading."),
    ("neutral", "Microsoft will hold its annual shareholder meeting on December 5."),
    ("neutral", "Nvidia announces the date of its next developer conference."),
]


def decide(url, model, state, question):
    body = json.dumps({"model": model, "state": state, "questions": {"q": question}}).encode()
    req = urllib.request.Request(f"{url}/api/decide", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        out = json.load(resp)
    answer = out["answers"]["q"]
    return answer["choice"], answer["probabilities"][answer["choice"]], out["total_duration"] / 1e6


def run_suite(url, models, title, question, cases):
    print(f"\n=== {title} ===")
    width = 34
    print(f"{'expected':<9} {'text':<{width}} " + " ".join(f"{m:>24}" for m in models))
    score = {m: 0 for m in models}
    times = {m: [] for m in models}
    for expected, text in cases:
        cells = []
        for m in models:
            label, prob, ms = decide(url, m, text, question)
            ok = label == expected
            score[m] += ok
            times[m].append(ms)
            cells.append(f"{'✓' if ok else '✗'} {label} {prob:.0%} {ms:6.0f}ms")
        short = text if len(text) <= width else text[: width - 1] + "…"
        print(f"{expected:<9} {short:<{width}} " + " ".join(f"{c:>24}" for c in cells))
    for m in models:
        first, rest = times[m][0], times[m][1:] or times[m]
        print(f"  {m}: {score[m]}/{len(cases)} correct, "
              f"median {sorted(rest)[len(rest) // 2]:.0f} ms (first call {first:.0f} ms incl. load)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("models", nargs="+")
    p.add_argument("--url", default="http://localhost:11435")
    a = p.parse_args()
    run_suite(a.url, a.models, "Telegram spam", SPAM_QUESTION, SPAM_CASES)
    run_suite(a.url, a.models, "Trading news sentiment", SENTIMENT_QUESTION, SENTIMENT_CASES)


if __name__ == "__main__":
    main()
