#!/usr/bin/env python3
import json, os, time, datetime, requests, pathlib

LITELLM = os.getenv("LITELLM_URL", "http://localhost:8000")
MODEL   = os.getenv("MODEL", "anthropic/claude-3-haiku-20240307")
BUDGET_DOLLARS_PER_DAY = float(os.getenv("BUDGET_DAILY", "2.00"))

base = pathlib.Path(__file__).resolve().parent
state_path = base / "state.json"
logs_dir = base / "logs"; logs_dir.mkdir(exist_ok=True)
log_path = logs_dir / f"run-{datetime.date.today().isoformat()}.jsonl"

def load_state():
    if state_path.exists():
        return json.loads(state_path.read_text())
    return {"date": str(datetime.date.today()), "spent": 0.0, "last_run_ts": 0}

def save_state(s): state_path.write_text(json.dumps(s, indent=2))

def estimate_cost(inp_tokens, out_tokens):
    # crude: Haiku ~$0.25/M in + $1.25/M out; Sonnet ~$3/M in + $15/M out (adjust if you switch)
    cin, cout = 0.25/1_000_000, 1.25/1_000_000
    return inp_tokens*cin + out_tokens*cout

def call_llm(prompt):
    r = requests.post(
        f"{LITELLM}/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.2,
            "user": os.getenv("AGENT_ID", "agent-default"),
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    msg = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})  # litellm often includes token counts
    return msg, usage

def main():
    st = load_state()
    # reset daily budget if day rolled
    today = str(datetime.date.today())
    if st["date"] != today:
        st = {"date": today, "spent": 0.0, "last_run_ts": 0}

    if st["spent"] >= BUDGET_DOLLARS_PER_DAY:
        print("Budget cap reached, skipping.")
        return

    # TODO: replace with real “delta” work; simple demo task:
    prompt = "Summarize the single most important thing I should do today for my 24/7 agent project in <120 chars>."

    try:
        msg, usage = call_llm(prompt)
        in_tok  = usage.get("prompt_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)
        cost = estimate_cost(in_tok, out_tok)
        st["spent"] += cost

        entry = {
            "ts": datetime.datetime.utcnow().isoformat()+"Z",
            "model": MODEL,
            "prompt": prompt,
            "response": msg,
            "usage": usage,
            "cost_est": round(cost, 6),
            "spent_today": round(st["spent"], 6)
        }
        with open(log_path, "a") as f: f.write(json.dumps(entry)+"\n")
        print(f"OK: ${entry['cost_est']} (spent today ${entry['spent_today']})")
    finally:
        save_state(st)

if __name__ == "__main__":
    main()