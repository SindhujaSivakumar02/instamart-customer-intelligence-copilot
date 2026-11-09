import csv
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "data" / "policies"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
STATE = ROOT / "state"
OUT.mkdir(exist_ok=True)
STATE.mkdir(exist_ok=True)

sys.path.insert(0, str(ROOT))
import mock_llm

# ---------- POLICY CHUNKING AND RETRIEVAL ----------
chunks = []

for path in sorted(POLICIES.glob("*.txt")):
    words = path.read_text(encoding="utf-8").split()
    for start in range(0, len(words), 30):
        part = words[start:start + 40]
        if part:
            chunks.append({
                "source": path.name,
                "text": " ".join(part)
            })
        if start + 40 >= len(words):
            break

def retrieve(query, k=3):
    q = set(query.lower().split())
    scored = []
    for c in chunks:
        words = set(c["text"].lower().split())
        score = len(q & words) / max(1, len(q))
        scored.append({
            "source": c["source"],
            "score": score,
            "text": c["text"]
        })
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:k]

def answer(question):
    results = retrieve(question)
    context = "\n".join(
        f'[{r["source"]}] {r["text"]}' for r in results
    )
    response = mock_llm.chat([
        {
            "role": "system",
            "content": (
                "POLICY ASSISTANT. Answer only from supplied policy context. "
                "If the answer is not in the context, say: "
                "I could not find the information in the supplied policies."
            )
        },
        {
            "role": "user",
            "content": f"CONTEXT:\n{context}\nQUESTION:\n{question}"
        }
    ])
    return response.choices[0].message.content, results

# ---------- TOOL FUNCTIONS ----------
DB = ROOT / "data" / "instamart.db"

def get_order(order_id):
    with sqlite3.connect(DB) as conn:
        row = conn.execute(
            "SELECT order_id,status,order_amount,delivery_minutes "
            "FROM orders WHERE order_id=?", (order_id,)
        ).fetchone()
    if not row:
        return {"error": "NOT_FOUND"}
    return {
        "order_id": row[0],
        "status": row[1],
        "order_amount": float(row[2]),
        "delivery_minutes": float(row[3]) if row[3] else None
    }

def calculate_refund(order):
    if order.get("error"):
        return 0.0
    if order["status"].lower() != "completed":
        return 0.0
    if order["delivery_minutes"] is not None and order["delivery_minutes"] > 45:
        return order["order_amount"]
    return 0.0

def ledger(tool, order_id, amount):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": tool,
        "order_id": order_id,
        "refund_inr": round(amount, 2)
    }
    with open(OUT / "refund_ledger.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def extract_order_id(message):
    import re
    match = re.search(r"ORD-\d{6}", message)
    return match.group(0) if match else None

# ---------- RUN SCENARIOS ----------
with open(RAW / "agent_scenarios.csv", newline="", encoding="utf-8-sig") as f:
    scenarios = list(csv.DictReader(f))

runs = []
ledger_path = OUT / "refund_ledger.jsonl"
ledger_path.write_text("", encoding="utf-8")

for s in scenarios:
    sid = s["scenario_id"]
    message = s["message"]
    order_id = extract_order_id(message)
    steps = []
    llm_calls = 0
    tokens = 0

    # Simulated ReAct tool workflow: each observation is recorded.
    llm_calls += 1
    tokens += mock_llm.est_tokens(message)

    if "[LOOP]" in message:
        status = "FALLBACK_MAX_ITERATIONS"
        final = "Human review required: iteration limit reached."
    elif not order_id:
        status = "NOT_FOUND"
        final = "Please provide a valid order ID."
    else:
        order = get_order(order_id)
        steps.append({"tool": "get_order", "args": {"order_id": order_id},
                      "observation": order})
        llm_calls += 1

        if order.get("error"):
            status = "NOT_FOUND"
            final = "Order not found. Human support can assist."
        elif order["status"].lower() != "completed":
            status = "DENIED"
            final = "Refund denied because the order is not completed."
        else:
            policy, sources = answer("refund policy late delivery")
            steps.append({"tool": "search_policy",
                          "args": {"query": "refund policy late delivery"},
                          "observation": {"answer": policy,
                                          "sources": [x["source"] for x in sources]}})
            llm_calls += 1
            amount = calculate_refund(order)
            steps.append({"tool": "calculate_refund",
                          "args": {"order_id": order_id},
                          "observation": {"refund_inr": amount}})
            llm_calls += 1

            if amount <= 0:
                status = "DENIED"
                final = "No refund is due under the delivery policy."
            elif amount > 1000:
                ledger("escalate_to_human", order_id, amount)
                steps.append({"tool": "escalate_to_human",
                              "args": {"order_id": order_id, "refund_inr": amount},
                              "observation": {"refund_inr": amount}})
                status = "ESCALATE"
                final = f"Refund of INR {amount:.2f} requires human approval."
            else:
                ledger("issue_refund", order_id, amount)
                steps.append({"tool": "issue_refund",
                              "args": {"order_id": order_id, "refund_inr": amount},
                              "observation": {"refund_inr": amount}})
                status = "REFUND"
                final = f"Refund of INR {amount:.2f} has been issued."

    run = {
        "scenario_id": sid,
        "status": status,
        "final_answer": final,
        "llm_calls": llm_calls,
        "tokens_used": tokens,
        "steps": steps
    }
    runs.append(run)

    with open(OUT / "agent_runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(run) + "\n")

    # Basic checkpoint after each scenario
    (STATE / f"{sid}.json").write_text(
        json.dumps(run, indent=2), encoding="utf-8"
    )

# ---------- SUMMARY ----------
print("PART D COMPLETE")
print("Policy chunks:", len(chunks))
print("Agent scenarios:", len(runs))
for r in runs:
    print(r["scenario_id"], r["status"], r["final_answer"])
print("Created agent_runs.jsonl")
print("Created refund_ledger.jsonl")
print("Created state checkpoints")
print("Policy test:", answer("What is the refund policy for late delivery?")[0])