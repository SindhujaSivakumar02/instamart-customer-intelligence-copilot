import csv
import re
import sys
import json
import time
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import mock_llm

RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

tickets = read_csv(RAW / "tickets.csv")
segments = read_csv(OUT / "customer_segments.csv")
premium = {s["customer_id"] for s in segments if str(s["is_premium"]) == "1"}

def redact(text):
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[EMAIL]", text)
    text = re.sub(r"\b[6-9]\d{9}\b", "[PHONE]", text)
    text = re.sub(r"ORD-\d{6}", "[ORDER_ID]", text)
    return text

def run_batch(fewshot=True, budget=100000):
    mock_llm.reset()
    rows = []
    total_tokens = 0
    retries = 0

    system = (
        'CLASSIFY support tickets. Classify into billing, delivery, technical, fraud. '
        'Return JSON only: {"category":"...","reason":"..."}'
    )
    if fewshot:
        system += (
            "\nEXAMPLES:\n"
            "Unauthorized account transaction -> fraud\n"
            "My delivery arrived late -> delivery\n"
            "The app crashes during login -> technical"
        )

    for ticket in tickets:
        original = ticket.get("text", "") or ""
        text = redact(original)
        status = ""
        category = ""
        used = 0

        if not text.strip():
            status = "skipped_empty"
        elif mock_llm.est_tokens(text) > 400:
            status = "flagged_long"
        elif total_tokens >= budget:
            status = "budget_exhausted"
        else:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": text}
            ]
            response = None
            for attempt in range(4):
                try:
                    response = mock_llm.chat(messages)
                    break
                except mock_llm.TransientLLMError:
                    if attempt == 3:
                        break
                    retries += 1
                    time.sleep(0.05 * (2 ** attempt) * random.uniform(0.9, 1.15))

            if response is None:
                status = "flagged_invalid_output"
            else:
                used = response.usage.total_tokens
                total_tokens += used
                answer = response.choices[0].message.content or ""
                try:
                    obj = json.loads(answer)
                    if obj.get("category") in ("billing", "delivery", "technical", "fraud"):
                        category = obj["category"]
                        status = "classified_json"
                    else:
                        status = "flagged_invalid_output"
                except Exception:
                    words = re.findall(r"[a-z]+", answer.lower())
                    matches = [w for w in words if w in ("billing", "delivery", "technical", "fraud")]
                    if len(set(matches)) == 1:
                        category = matches[0]
                        status = "classified_keyword"
                    else:
                        status = "flagged_invalid_output"

        if status in ("skipped_empty", "flagged_long", "flagged_invalid_output", "budget_exhausted"):
            priority, route = "NORMAL", "human_review"
        elif category == "fraud":
            priority, route = "HIGH", "security_team"
        elif ticket["customer_id"] in premium:
            priority, route = "HIGH", "premium_desk"
        else:
            priority, route = "NORMAL", "support_queue"

        rows.append({
            "ticket_id": ticket["ticket_id"],
            "customer_id": ticket["customer_id"],
            "status": status,
            "category": category,
            "segment_name": next(
                (s["segment_name"] for s in segments if s["customer_id"] == ticket["customer_id"]), ""
            ),
            "priority": priority,
            "route": route,
            "tokens_used": used
        })

    return rows, total_tokens, retries

# Zero-shot budget demonstration
zero_rows, zero_tokens, zero_retries = run_batch(False, 6000)
write_csv(OUT / "triage_budget_demo.csv", zero_rows)

# Final few-shot run
final_rows, final_tokens, final_retries = run_batch(True, 100000)
write_csv(OUT / "triage_results.csv", final_rows)

print("PART C COMPLETE")
print("Tickets:", len(final_rows))
print("Statuses:")
for status in sorted(set(r["status"] for r in final_rows)):
    print(status, sum(r["status"] == status for r in final_rows))
print("Few-shot tokens:", final_tokens)
print("Few-shot retries:", final_retries)
print("Zero-shot budget tokens:", zero_tokens)
print("Zero-shot budget exhausted:", sum(r["status"] == "budget_exhausted" for r in zero_rows))
print("Created triage_results.csv and triage_budget_demo.csv")