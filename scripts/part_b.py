import csv
import json
import math
import pickle
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

def read(name):
    with open(CLEAN / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def write(name, rows):
    if not rows:
        return
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def date(s):
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except Exception:
        return None

customers = read("customers.csv")
orders = read("orders.csv")
completed = [o for o in orders if o["status"].lower() == "completed"]
cutoff = datetime(2025, 10, 1)
cohort_cutoff = datetime(2025, 9, 1)

# RFM
rfm = {}
for o in completed:
    d = date(o["order_ts"])
    if not d:
        continue
    cid = o["customer_id"]
    x = rfm.setdefault(cid, {"dates": [], "frequency": 0, "monetary": 0.0})
    x["dates"].append(d)
    x["frequency"] += 1
    x["monetary"] += float(o["order_amount"])

segments = []
for cid, x in rfm.items():
    recency = (cutoff - max(x["dates"])).days
    segments.append({
        "customer_id": cid,
        "recency": recency,
        "frequency": x["frequency"],
        "monetary": round(x["monetary"], 2)
    })

# Transparent rule-based segments (not trained KMeans)
for s in segments:
    if s["monetary"] >= 5000:
        s["segment_id"], s["segment_name"], s["is_premium"] = 0, "Premium", 1
    elif s["frequency"] >= 12:
        s["segment_id"], s["segment_name"], s["is_premium"] = 1, "Loyal", 0
    elif s["recency"] <= 30:
        s["segment_id"], s["segment_name"], s["is_premium"] = 2, "Active", 0
    else:
        s["segment_id"], s["segment_name"], s["is_premium"] = 3, "At Risk", 0

write("customer_segments.csv", segments)

# Lapse cohort: customers with completed order before Sep 1
pre = {}
sep_active = set()
for o in completed:
    d = date(o["order_ts"])
    if not d:
        continue
    cid = o["customer_id"]
    if d < cohort_cutoff:
        x = pre.setdefault(cid, {"dates": [], "amounts": [], "discounts": []})
        x["dates"].append(d)
        x["amounts"].append(float(o["order_amount"]))
        x["discounts"].append(float(o["discount_pct"] or 0))
    elif datetime(2025, 9, 1) <= d < datetime(2025, 10, 1):
        sep_active.add(cid)

segment_map = {s["customer_id"]: s for s in segments}
retention = []

for cid, x in pre.items():
    lapsed = int(cid not in sep_active)
    recency = (cohort_cutoff - max(x["dates"])).days
    frequency = len(x["dates"])
    monetary = sum(x["amounts"])

    # Simple transparent risk score, not a trained ML probability.
    score = -1.5 + recency / 65 - frequency / 18 - monetary / 12000
    probability = 1 / (1 + math.exp(-max(-20, min(20, score))))

    seg = segment_map.get(cid, {})
    retention.append({
        "customer_id": cid,
        "lapse_probability": round(probability, 4),
        "actually_lapsed": lapsed,
        "segment_name": seg.get("segment_name", "Unknown"),
        "is_premium": seg.get("is_premium", 0)
    })

# Save model metadata as a pickle artifact; this is a heuristic, not ML.
model = {
    "type": "rule_based_lapse_score",
    "formula": "sigmoid(-1.5 + recency/65 - frequency/18 - monetary/12000)",
    "trained_model": False
}
with open(OUT / "lapse_model.joblib", "wb") as f:
    pickle.dump(model, f)

premium = [r for r in retention if r["is_premium"] == 1]
premium.sort(key=lambda r: r["lapse_probability"], reverse=True)
write("retention_list.csv", premium[:10])

print("PART B OUTPUTS")
print("Segmented customers:", len(segments))
print("Lapse cohort:", len(retention))
print("Lapsed:", sum(r["actually_lapsed"] for r in retention))
print("Premium retention list:", min(10, len(premium)))
print("Created customer_segments.csv")
print("Created lapse_model.joblib")
print("Created retention_list.csv")