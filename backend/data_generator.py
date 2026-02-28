"""
Synthetic Financial Network Data Generator
Generates realistic transaction data for fraud detection system.
"""

import random
import json
import uuid
from datetime import datetime, timedelta

random.seed(42)

CHANNELS = ["UPI", "Wallet", "ATM", "NEFT", "IMPS"]
ACCOUNT_TYPES = ["personal", "business"]
COUNTRIES = ["IN", "IN", "IN", "IN", "US", "AE", "SG"]  # India-heavy

def generate_account_id(prefix="ACC"):
    return f"{prefix}_{uuid.uuid4().hex[:8].upper()}"

def random_timestamp(base, max_offset_minutes=1440):
    offset = random.uniform(0, max_offset_minutes * 60)
    return base + timedelta(seconds=offset)

def generate_transaction(source, destination, amount, timestamp, channel, 
                          account_type_src="personal", account_age_src=365,
                          country="IN"):
    return {
        "transaction_id": f"TXN_{uuid.uuid4().hex[:12].upper()}",
        "source": source,
        "destination": destination,
        "amount": round(amount, 2),
        "timestamp": timestamp.isoformat() + "Z",
        "channel": channel,
        "account_type": account_type_src,
        "account_age": account_age_src,
        "country_code": country
    }

def generate_dataset():
    base_time = datetime(2024, 1, 15, 8, 0, 0)
    transactions = []
    accounts = {}

    # ── Normal Users (20 accounts) ──────────────────────────────────
    normal_accounts = [generate_account_id("NORM") for _ in range(20)]
    for acc in normal_accounts:
        accounts[acc] = {"type": "personal", "age": random.randint(365, 2000), "country": "IN"}

    # Salary credits (monthly from employer)
    employer = generate_account_id("EMP")
    accounts[employer] = {"type": "business", "age": 1800, "country": "IN"}
    for acc in normal_accounts:
        salary_time = base_time + timedelta(days=random.randint(0, 2), hours=random.randint(9, 11))
        transactions.append(generate_transaction(
            employer, acc, random.uniform(30000, 80000), salary_time,
            "NEFT", "business", accounts[employer]["age"], "IN"
        ))

    # Regular bill payments
    utilities = [generate_account_id("UTIL") for _ in range(5)]
    for acc in normal_accounts:
        for _ in range(random.randint(2, 5)):
            t = random_timestamp(base_time, 720)
            dest = random.choice(utilities)
            transactions.append(generate_transaction(
                acc, dest, random.uniform(500, 5000), t,
                random.choice(["UPI", "Wallet"]),
                "personal", accounts[acc]["age"], "IN"
            ))

    # Moderate peer transfers
    for _ in range(30):
        src, dst = random.sample(normal_accounts, 2)
        t = random_timestamp(base_time, 720)
        transactions.append(generate_transaction(
            src, dst, random.uniform(100, 10000), t,
            random.choice(["UPI", "IMPS"]),
            "personal", accounts[src]["age"], "IN"
        ))

    # ── Business Users (5 accounts) ────────────────────────────────
    business_accounts = [generate_account_id("BIZ") for _ in range(5)]
    vendors = [generate_account_id("VND") for _ in range(10)]
    for acc in business_accounts:
        accounts[acc] = {"type": "business", "age": random.randint(180, 1500), "country": "IN"}
    for v in vendors:
        accounts[v] = {"type": "business", "age": random.randint(90, 900), "country": "IN"}

    for biz in business_accounts:
        for _ in range(random.randint(15, 30)):
            t = random_timestamp(base_time, 720)
            vnd = random.choice(vendors)
            transactions.append(generate_transaction(
                biz, vnd, random.uniform(5000, 200000), t,
                random.choice(["NEFT", "IMPS", "UPI"]),
                "business", accounts[biz]["age"], "IN"
            ))

    # ── Mule Chain Attack (Full: Source → Mule A → Mule B → Mule C → ATM) ─
    fraud_source = generate_account_id("FRAUD")
    mule_a = generate_account_id("MULE")
    mule_b = generate_account_id("MULE")
    mule_c = generate_account_id("MULE")
    atm_node = generate_account_id("ATM")

    accounts[fraud_source] = {"type": "personal", "age": 12, "country": "AE"}
    accounts[mule_a] = {"type": "personal", "age": 8, "country": "IN"}
    accounts[mule_b] = {"type": "personal", "age": 15, "country": "IN"}
    accounts[mule_c] = {"type": "personal", "age": 6, "country": "IN"}
    accounts[atm_node] = {"type": "personal", "age": 3, "country": "IN"}

    attack_base = base_time + timedelta(hours=6)
    t1 = attack_base
    t2 = attack_base + timedelta(minutes=4)
    t3 = attack_base + timedelta(minutes=9)
    t4 = attack_base + timedelta(minutes=13)

    mule_chain = [
        generate_transaction(fraud_source, mule_a, 95000, t1, "UPI", "personal", 12, "AE"),
        generate_transaction(mule_a, mule_b, 92000, t2, "Wallet", "personal", 8, "IN"),
        generate_transaction(mule_b, mule_c, 89000, t3, "UPI", "personal", 15, "IN"),
        generate_transaction(mule_c, atm_node, 85000, t4, "ATM", "personal", 6, "IN"),
    ]
    transactions.extend(mule_chain)

    # ── Partial Mule (2 hops only) ─────────────────────────────────
    p_fraud = generate_account_id("FRAUD")
    p_mule1 = generate_account_id("MULE")
    p_mule2 = generate_account_id("MULE")
    accounts[p_fraud] = {"type": "personal", "age": 5, "country": "SG"}
    accounts[p_mule1] = {"type": "personal", "age": 10, "country": "IN"}
    accounts[p_mule2] = {"type": "personal", "age": 7, "country": "IN"}

    pt_base = base_time + timedelta(hours=10)
    transactions.extend([
        generate_transaction(p_fraud, p_mule1, 45000, pt_base, "UPI", "personal", 5, "SG"),
        generate_transaction(p_mule1, p_mule2, 43000, pt_base + timedelta(minutes=7), "ATM", "personal", 10, "IN"),
    ])

    # Sort by timestamp
    transactions.sort(key=lambda x: x["timestamp"])

    # Build account metadata
    account_meta = {}
    for acc_id, meta in accounts.items():
        account_meta[acc_id] = {
            "account_id": acc_id,
            "account_type": meta["type"],
            "account_age": meta["age"],
            "country_code": meta["country"]
        }

    dataset = {
        "transactions": transactions,
        "accounts": account_meta,
        "scenario_accounts": {
            "normal_sample": normal_accounts[0],
            "business_sample": business_accounts[0],
            "fraud_source": fraud_source,
            "mule_a": mule_a,
            "mule_b": mule_b,
            "mule_c": mule_c,
            "atm_node": atm_node,
            "partial_mule1": p_mule1,
            "partial_mule2": p_mule2
        }
    }

    return dataset


if __name__ == "__main__":
    data = generate_dataset()
    with open("/home/claude/fraud_system/synthetic_data.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Generated {len(data['transactions'])} transactions across {len(data['accounts'])} accounts")
    print("Scenario accounts:", json.dumps(data['scenario_accounts'], indent=2))
