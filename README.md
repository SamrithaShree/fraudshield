# FraudShield: Security-First ML Anomaly Detection

**FraudShield** is an advanced, multi-layered fraud detection system designed for high-velocity transaction monitoring. It combines graph-based temporal analysis with an adaptive, analyst-informed risk scoring engine to intercept financial crime in real-time.

---

## Security Posture

### 1. ML-Based Anomaly Detection (Adaptive Weights)
FraudShield utilizes a **dynamic scoring engine** that adapts based on empirical evidence:
- **Feature-Based Scoring:** Transactions are scored across 6+ vectors including velocity, multi-hop "layering" patterns, and channel switching.
- **Closed-Loop Feedback:** Confirmed fraud cases automatically reinforce feature weights, while false positives trigger weight decay, ensuring the engine remains tuned to emerging threat vectors.
- **Temporal Graph Analysis:** Detects "mule networks" by analyzing the journey of funds across nodes with millisecond precision.

### 2. Role-Based Access Control (RBAC)
The system is architected for strict separation of duties and least privilege:
- **System Service:** High-throughput, read-only access to transaction streams for risk scoring.
- **Fraud Analyst (Role):** Authorized to review flagged transactions, override scores, and trigger manual weight adjustments.
- **Security Administrator (Role):** Manages thresholds, intercept logic, and system-wide security configurations.
- **Audit Logging:** Every scoring adjustment and manual intervention is logged with a cryptographic-friendly timestamp for forensic accountability.

### 3. Threat Mitigation Strategies
- **Exit-Point Interception:** Special scrutiny for irreversible channels (ATM, Crypto, External Transfers) to prevent fund exfiltration.
- **Risk Propagation:** Uses a **Neighbor Scrutiny Engine** to temporarily flag accounts associated with confirmed malicious entities.
- **Step-Up Verification:** Integrated triggers for multi-factor authentication (MFA) on high-risk, non-critical transactions.

---

## Getting Started

### Prerequisites
- Python 3.9+
- Node.js 18+ (for Analyst UI)

### Installation
1. **Backend Setup:**
   ```bash
   pip install -r requirements.txt
   python backend/orchestrator.py
   ```
2. **Frontend Setup:**
   ```bash
   cd frontend
   npm install && npm run dev
   ```

---

## Security Validation

Run the security test suite to verify intercept logic:
```bash
pytest tests/security_scenarios.py
```

### OWASP Best Practices Applied
- **A01:2021-Broken Access Control:** Enforced via RBAC-ready analyst endpoints.
- **A03:2021-Injection:** All input data is sanitized through the `DecisionEngine` validation layer.
- **A09:2021-Security Logging and Monitoring:** Comprehensive scoring and decision logs.

---

## Contributing
Please review our `SECURITY.md` (Draft) before submitting PRs. All changes must pass the automated threat model validation.
