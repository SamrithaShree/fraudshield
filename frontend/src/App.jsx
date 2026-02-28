import { useState } from "react";

const ATTACK_CHAIN = [
  {
    tx: { transaction_id: "TXN_ATK_1", source: "FRAUD_C147", destination: "MULE_D2C1", amount: 95000, channel: "UPI", account_age: 12, country_code: "AE", timestamp: "2024-01-15T16:00:00Z" },
    score: 28.7, action: "ALLOW", message: "Transaction within normal parameters. Proceeding.",
    reasons: ["Short-lived account: 12 days old", "Cross-border risk: source country AE"],
    paths: [],
    feature_scores: { velocity_score: 0, hop_score: 0.2, channel_switch_score: 0, new_account_penalty: 0.85, cross_border_penalty: 1.0, amount_concentration_score: 0.5 },
    cashout: false
  },
  {
    tx: { transaction_id: "TXN_ATK_2", source: "MULE_D2C1", destination: "MULE_40A3", amount: 92000, channel: "Wallet", account_age: 8, country_code: "IN", timestamp: "2024-01-15T16:04:00Z" },
    score: 52.3, action: "MONITOR", message: "Elevated risk detected. Transaction allowed with enhanced monitoring.",
    reasons: ["Multi-hop money movement detected (2 hops)", "Time-compressed layering: rapid sequential transfers", "Short-lived account: 8 days old"],
    paths: [{ path: ["FRAUD_C147", "MULE_D2C1", "MULE_40A3"], hops: 2, time_min: 4, cashout: false, channels: ["UPI", "Wallet"] }],
    feature_scores: { velocity_score: 0, hop_score: 0.55, channel_switch_score: 0.35, new_account_penalty: 1.0, cross_border_penalty: 0, amount_concentration_score: 0.3 },
    cashout: false
  },
  {
    tx: { transaction_id: "TXN_ATK_3", source: "MULE_40A3", destination: "MULE_2668", amount: 89000, channel: "UPI", account_age: 15, country_code: "IN", timestamp: "2024-01-15T16:09:00Z" },
    score: 62.0, action: "MONITOR", message: "Elevated risk detected. Transaction allowed with enhanced monitoring.",
    reasons: ["Multi-hop money movement detected (3 hops)", "Time-compressed layering: rapid sequential transfers", "Short-lived account: 15 days old"],
    paths: [{ path: ["FRAUD_C147", "MULE_D2C1", "MULE_40A3", "MULE_2668"], hops: 3, time_min: 9, cashout: false, channels: ["UPI", "Wallet", "UPI"] }],
    feature_scores: { velocity_score: 0.3, hop_score: 0.9, channel_switch_score: 0.7, new_account_penalty: 0.85, cross_border_penalty: 0, amount_concentration_score: 0.4 },
    cashout: false
  },
  {
    tx: { transaction_id: "TXN_ATK_4", source: "MULE_2668", destination: "ATM_F912", amount: 85000, channel: "ATM", account_age: 6, country_code: "IN", timestamp: "2024-01-15T16:13:00Z" },
    score: 68.8, action: "INTERCEPT", message: "EXIT-POINT INTERCEPT: ATM withdrawal of Rs.85,000 blocked. Funds cannot be recovered once dispensed. Flagged for immediate analyst review.",
    reasons: ["Multi-hop money movement detected (3 hops)", "Time-compressed layering: rapid sequential transfers", "Channel switching detected (2 switches) — layering pattern", "ATM cashout detected at terminal hop — exit-point risk", "Short-lived account: 6 days old"],
    paths: [
      { path: ["MULE_D2C1", "MULE_40A3", "MULE_2668", "ATM_F912"], hops: 3, time_min: 9, cashout: true, channels: ["Wallet", "UPI", "ATM"] },
      { path: ["FRAUD_C147", "MULE_D2C1", "MULE_40A3", "MULE_2668"], hops: 3, time_min: 9, cashout: false, channels: ["UPI", "Wallet", "UPI"] },
    ],
    feature_scores: { velocity_score: 0.6, hop_score: 0.9, channel_switch_score: 1.0, new_account_penalty: 1.0, cross_border_penalty: 0, amount_concentration_score: 0.5 },
    cashout: true
  },
];

const WEIGHTS_BEFORE = { velocity_score: 0.25, hop_score: 0.30, channel_switch_score: 0.15, new_account_penalty: 0.15, cross_border_penalty: 0.10, amount_concentration_score: 0.05 };
const WEIGHTS_AFTER  = { velocity_score: 0.2174, hop_score: 0.3043, channel_switch_score: 0.1739, new_account_penalty: 0.1739, cross_border_penalty: 0.087, amount_concentration_score: 0.0435 };

const NORMAL_FEATURES  = { velocity_score: 0, hop_score: 0.2, channel_switch_score: 0, new_account_penalty: 0, cross_border_penalty: 0, amount_concentration_score: 0.1 };
const BIZ_FEATURES     = { velocity_score: 0.3, hop_score: 0.2, channel_switch_score: 0, new_account_penalty: 0, cross_border_penalty: 0, amount_concentration_score: 0.4 };

const FEATURE_LABELS = {
  velocity_score:            "Velocity Score",
  hop_score:                 "Hop Score",
  channel_switch_score:      "Channel Switch Score",
  new_account_penalty:       "New Account Penalty",
  cross_border_penalty:      "Cross-Border Penalty",
  amount_concentration_score:"Amount Concentration",
};

const scoreColor = (s) => s < 40 ? "#16a34a" : s < 70 ? "#b45309" : s < 85 ? "#dc2626" : "#b91c1c";

const ACTION_META = {
  ALLOW:                { color: "#16a34a", dimColor: "#052e16", borderColor: "#166534" },
  MONITOR:              { color: "#b45309", dimColor: "#1c1000", borderColor: "#78350f" },
  STEP_UP_VERIFICATION: { color: "#dc2626", dimColor: "#1c0303", borderColor: "#991b1b" },
  INTERCEPT:            { color: "#b91c1c", dimColor: "#150000", borderColor: "#7f1d1d" },
  DELAY_WITHDRAWAL:     { color: "#c2410c", dimColor: "#1c0800", borderColor: "#9a3412" },
};

// ── GAUGE ──────────────────────────────────────────────────────────────────
function GaugeArc({ score }) {
  const r = 66, cx = 86, cy = 86;
  const toRad = (a) => (a * Math.PI) / 180;
  const sweep = 180 * (score / 100);
  const endA  = 180 + sweep;
  const x1    = cx + r * Math.cos(toRad(180));
  const y1    = cy + r * Math.sin(toRad(180));
  const x2    = cx + r * Math.cos(toRad(endA));
  const y2    = cy + r * Math.sin(toRad(endA));
  const bgx2  = cx + r * Math.cos(toRad(360));
  const bgy2  = cy + r * Math.sin(toRad(360));
  const large = sweep > 180 ? 1 : 0;
  const col   = scoreColor(score);

  return (
    <svg width="172" height="94" viewBox="0 0 172 94" style={{ display: "block" }}>
      <path d={`M ${x1} ${y1} A ${r} ${r} 0 0 1 ${bgx2} ${bgy2}`}
        fill="none" stroke="#111827" strokeWidth="11" strokeLinecap="round" />
      {score > 0 && (
        <path d={`M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`}
          fill="none" stroke={col} strokeWidth="11" strokeLinecap="round" />
      )}
      <text x={cx} y={cy - 7} textAnchor="middle" fill={col}
        fontSize="27" fontWeight="700" fontFamily="monospace">{score.toFixed(0)}</text>
      <text x={cx} y={cy + 9} textAnchor="middle" fill="#374151"
        fontSize="8" fontFamily="monospace" letterSpacing="2">RISK SCORE</text>
    </svg>
  );
}

// ── FEATURE BAR ────────────────────────────────────────────────────────────
function FeatureBar({ label, value, weight }) {
  const pct  = Math.round(value * 100);
  const wPct = Math.round(weight * 100);
  const col  = pct > 70 ? "#dc2626" : pct > 40 ? "#b45309" : "#16a34a";
  return (
    <div style={{ marginBottom: 11 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ color: "#6b7280", fontSize: 11, fontFamily: "monospace" }}>{label}</span>
        <span style={{ color: "#9ca3af", fontSize: 11, fontFamily: "monospace" }}>
          {pct}%<span style={{ color: "#374151", marginLeft: 8 }}>w = {wPct}%</span>
        </span>
      </div>
      <div style={{ background: "#111827", borderRadius: 2, height: 4, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: col, borderRadius: 2, transition: "width 0.5s ease" }} />
      </div>
    </div>
  );
}

// ── PATH VISUALISER ────────────────────────────────────────────────────────
function PathViz({ paths }) {
  if (!paths || paths.length === 0) {
    return (
      <p style={{ color: "#374151", fontSize: 12, fontFamily: "monospace", margin: 0 }}>
        No multi-hop paths detected within the 30-minute temporal window.
      </p>
    );
  }
  return (
    <div>
      {paths.slice(0, 2).map((p, i) => (
        <div key={i} style={{ marginBottom: 12, background: "#0a1020", borderRadius: 4, padding: "12px 14px", border: p.cashout ? "1px solid #7f1d1d" : "1px solid #111827" }}>
          <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 0, marginBottom: 10 }}>
            {p.path.map((node, j) => (
              <div key={j} style={{ display: "flex", alignItems: "center" }}>
                <div style={{
                  padding: "3px 10px", borderRadius: 3, fontSize: 11, fontFamily: "monospace",
                  background: j === 0 ? "#0c1d36" : j === p.path.length - 1 && p.cashout ? "#1a0000" : "#111827",
                  color:      j === 0 ? "#60a5fa" : j === p.path.length - 1 && p.cashout ? "#f87171" : "#6b7280",
                  border:     j === 0 ? "1px solid #1e3a5f" : j === p.path.length - 1 && p.cashout ? "1px solid #7f1d1d" : "1px solid #1f2937",
                }}>
                  {node}
                </div>
                {j < p.path.length - 1 && (
                  <div style={{ display: "flex", alignItems: "center", padding: "0 8px", gap: 4 }}>
                    <span style={{ fontSize: 9, color: "#374151", fontFamily: "monospace" }}>{p.channels[j]}</span>
                    <div style={{ width: 16, height: 1, background: "#374151" }} />
                    <div style={{ width: 0, height: 0, borderTop: "3px solid transparent", borderBottom: "3px solid transparent", borderLeft: "5px solid #374151" }} />
                  </div>
                )}
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 24, fontSize: 10, fontFamily: "monospace", color: "#374151" }}>
            <span>{p.hops} {p.hops === 1 ? "hop" : "hops"}</span>
            <span>{p.time_min} min</span>
            <span style={{ color: p.cashout ? "#f87171" : "#374151" }}>
              {p.cashout ? "CASHOUT EXIT" : "IN-FLIGHT"}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── DECISION BADGE ─────────────────────────────────────────────────────────
function DecisionBadge({ action, message }) {
  const m = ACTION_META[action] || { color: "#6b7280", dimColor: "#111827", borderColor: "#1f2937" };
  return (
    <div style={{ background: m.dimColor, border: `1px solid ${m.borderColor}`, borderRadius: 5, padding: "13px 16px", marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: m.color, flexShrink: 0 }} />
        <span style={{ color: m.color, fontFamily: "monospace", fontWeight: 700, fontSize: 12, letterSpacing: 3 }}>
          {action.replace(/_/g, " ")}
        </span>
      </div>
      <p style={{ color: "#6b7280", fontSize: 12, margin: 0, fontFamily: "monospace", lineHeight: 1.65 }}>{message}</p>
    </div>
  );
}

// ── WEIGHT COMPARE ─────────────────────────────────────────────────────────
function WeightCompare({ before, after }) {
  return (
    <div style={{ background: "#0a1020", border: "1px solid #111827", borderRadius: 5, padding: 16 }}>
      <div style={{ color: "#374151", fontFamily: "monospace", fontSize: 9, letterSpacing: 3, marginBottom: 14 }}>
        ADAPTIVE WEIGHT DELTA — POST ANALYST FEEDBACK
      </div>
      {Object.keys(before).map((k) => {
        const diff = (after[k] - before[k]) * 100;
        const isUp = diff > 0.01;
        const isDn = diff < -0.01;
        return (
          <div key={k} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 9, fontFamily: "monospace" }}>
            <span style={{ color: "#4b5563", fontSize: 11 }}>{FEATURE_LABELS[k]}</span>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ color: "#374151", fontSize: 11 }}>{(before[k] * 100).toFixed(1)}%</span>
              <span style={{ color: "#1f2937" }}>→</span>
              <span style={{ color: isUp ? "#b45309" : isDn ? "#3b82f6" : "#9ca3af", fontSize: 11, fontWeight: 600, minWidth: 38, textAlign: "right" }}>
                {(after[k] * 100).toFixed(1)}%
              </span>
              <span style={{ fontSize: 10, color: isUp ? "#b45309" : isDn ? "#3b82f6" : "#1f2937", minWidth: 38 }}>
                {isUp ? `+${Math.abs(diff).toFixed(1)}` : isDn ? `-${Math.abs(diff).toFixed(1)}` : "—"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── MAIN ───────────────────────────────────────────────────────────────────
export default function FraudShield() {
  const [scenario,     setScenario]     = useState("normal");
  const [attackStep,   setAttackStep]   = useState(0);
  const [animating,    setAnimating]    = useState(false);
  const [feedbackDone, setFeedbackDone] = useState(false);
  const [tab,          setTab]          = useState("overview");

  const atk = ATTACK_CHAIN[attackStep];

  const score    = scenario === "attack" ? atk.score    : 6.0;
  const action   = scenario === "attack" ? atk.action   : "ALLOW";
  const reasons  = scenario === "attack" ? atk.reasons  : ["Transaction within normal behavioral parameters"];
  const features = scenario === "attack" ? atk.feature_scores : scenario === "business" ? BIZ_FEATURES : NORMAL_FEATURES;

  const injectNext = () => {
    if (animating || attackStep >= ATTACK_CHAIN.length - 1) return;
    setAnimating(true);
    setTimeout(() => { setAttackStep(s => s + 1); setAnimating(false); }, 280);
  };

  const switchScenario = (s) => {
    setScenario(s); setAttackStep(0); setFeedbackDone(false); setTab("overview");
  };

  const txMeta = scenario === "normal"
    ? { id: "TXN_SALARY_001", from: "EMP_CORP01", to: "NORM_194E",    amount: "2,500",  channel: "UPI",    age: "1,200", country: "IN" }
    : scenario === "business"
    ? { id: "TXN_BIZ_042",    from: "BIZ_9801",   to: "VND_ALPHA3",  amount: "75,000", channel: "NEFT",   age: "450",   country: "IN" }
    : { id: atk.tx.transaction_id, from: atk.tx.source, to: atk.tx.destination, amount: atk.tx.amount.toLocaleString(), channel: atk.tx.channel, age: String(atk.tx.account_age), country: atk.tx.country_code };

  const S = {
    // colours
    bg:       "#020810",
    surface:  "#060d1a",
    surface2: "#0a1220",
    border:   "#0f1a2e",
    border2:  "#111827",
    muted:    "#374151",
    sub:      "#1f2937",
    text:     "#9ca3af",
    bright:   "#d1d5db",
    accent:   "#3b82f6",
    // spacing helpers
    card: { background: "#060d1a", border: "1px solid #0f1a2e", borderRadius: 5, padding: "16px 18px" },
    label: { fontSize: 9, color: "#374151", letterSpacing: 3, fontFamily: "monospace", marginBottom: 10 },
  };

  return (
    <div style={{ background: S.bg, minHeight: "100vh", color: S.bright, fontFamily: "monospace", display: "flex", flexDirection: "column" }}>

      {/* HEADER */}
      <div style={{ borderBottom: `1px solid ${S.border}`, padding: "0 28px", height: 54, display: "flex", alignItems: "center", justifyContent: "space-between", background: "#030b16", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 2, height: 20, background: S.accent }} />
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: 4, color: S.bright }}>FRAUDSHIELD</div>
            <div style={{ fontSize: 8, color: S.muted, letterSpacing: 3, marginTop: 2 }}>TEMPORAL GRAPH DETECTION ENGINE</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#16a34a" }} />
            <span style={{ fontSize: 10, color: "#16a34a", letterSpacing: 2 }}>OPERATIONAL</span>
          </div>
          <span style={{ fontSize: 10, color: S.muted }}>237 transactions · 44 accounts</span>
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

        {/* LEFT SIDEBAR */}
        <div style={{ width: 228, borderRight: `1px solid ${S.border}`, padding: "18px 14px", overflowY: "auto", background: "#030b16", flexShrink: 0 }}>

          <div style={S.label}>SCENARIO</div>
          {[
            { id: "normal",   label: "Normal User",  sub: "Salary / UPI / LOW RISK" },
            { id: "business", label: "Business User", sub: "Vendor / NEFT / LOW RISK" },
            { id: "attack",   label: "Mule Attack",   sub: "4-hop chain / INTERCEPT" },
          ].map((s) => (
            <button key={s.id} onClick={() => switchScenario(s.id)} style={{
              width: "100%", textAlign: "left",
              background: scenario === s.id ? "#0b1a30" : "transparent",
              border: `1px solid ${scenario === s.id ? "#1d4ed8" : S.border}`,
              borderRadius: 4, padding: "9px 11px", marginBottom: 5, cursor: "pointer",
            }}>
              <div style={{ fontSize: 12, color: scenario === s.id ? "#93c5fd" : S.text, marginBottom: 2 }}>{s.label}</div>
              <div style={{ fontSize: 9, color: S.muted }}>{s.sub}</div>
            </button>
          ))}

          {scenario === "attack" && (
            <div style={{ marginTop: 18 }}>
              <div style={S.label}>CHAIN REPLAY</div>
              {ATTACK_CHAIN.map((step, i) => {
                const past   = i < attackStep;
                const active = i === attackStep;
                const col    = ACTION_META[step.action]?.color || S.text;
                return (
                  <div key={i} onClick={() => i <= attackStep && setAttackStep(i)}
                    style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 9px", borderRadius: 4, marginBottom: 4, cursor: i <= attackStep ? "pointer" : "default", background: active ? "#0b1a30" : "transparent", border: `1px solid ${active ? S.border2 : "transparent"}` }}>
                    <div style={{
                      width: 20, height: 20, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 9, fontWeight: 700, flexShrink: 0,
                      background: past ? "#16a34a18" : active ? "#1d4ed818" : S.border2,
                      border: `1px solid ${past ? "#16a34a" : active ? "#3b82f6" : S.muted}`,
                      color: past ? "#16a34a" : active ? "#60a5fa" : S.muted,
                    }}>
                      {past ? "+" : i + 1}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 10, color: active ? S.bright : past ? "#4b5563" : S.sub }}>TXN_ATK_{i + 1}</div>
                      <div style={{ fontSize: 9, color: S.muted }}>{step.tx.channel} · Rs.{(step.tx.amount / 1000).toFixed(0)}K</div>
                    </div>
                    <div style={{ fontSize: 10, color: col }}>{i <= attackStep ? step.score.toFixed(0) : "—"}</div>
                  </div>
                );
              })}

              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
                {attackStep < ATTACK_CHAIN.length - 1 && (
                  <button onClick={injectNext} disabled={animating} style={{
                    width: "100%", background: "#0f2a5c", border: "1px solid #1d4ed8",
                    borderRadius: 4, padding: "8px 0", color: "#93c5fd", cursor: "pointer",
                    fontSize: 11, letterSpacing: 2, fontFamily: "monospace",
                  }}>
                    INJECT NEXT TXN
                  </button>
                )}
                {attackStep === ATTACK_CHAIN.length - 1 && !feedbackDone && (
                  <button onClick={() => { setFeedbackDone(true); setTab("feedback"); }} style={{
                    width: "100%", background: "#1e0a4a", border: "1px solid #6d28d9",
                    borderRadius: 4, padding: "8px 0", color: "#c4b5fd", cursor: "pointer",
                    fontSize: 11, letterSpacing: 2, fontFamily: "monospace",
                  }}>
                    ANALYST CONFIRM
                  </button>
                )}
                {feedbackDone && (
                  <div style={{ background: "#052e16", border: "1px solid #166534", borderRadius: 4, padding: "9px 12px", fontSize: 10, color: "#4ade80", lineHeight: 1.8 }}>
                    Feedback applied<br />Weights updated<br />2 neighbors flagged
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Pipeline steps */}
          <div style={{ marginTop: 26 }}>
            <div style={S.label}>PIPELINE</div>
            {[
              ["01", "Tx Event",       "Incoming transaction"],
              ["02", "Graph Update",   "Add edge to DiGraph"],
              ["03", "Window Extract", "30-min sliding window"],
              ["04", "BFS Journey",    "Depth-bounded traversal"],
              ["05", "Risk Score",     "Weighted feature sum"],
              ["06", "Decision",       "Threshold classify"],
              ["07", "Exit-Point",     "ATM re-evaluation"],
              ["08", "Feedback",       "Adapt weights"],
            ].map(([n, label, desc]) => (
              <div key={n} style={{ display: "flex", gap: 8, marginBottom: 7 }}>
                <span style={{ fontSize: 9, color: "#1d3a6e", fontWeight: 700, minWidth: 18, paddingTop: 1 }}>{n}</span>
                <div>
                  <div style={{ fontSize: 10, color: "#4b5563" }}>{label}</div>
                  <div style={{ fontSize: 9, color: S.sub }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Components */}
          <div style={{ marginTop: 18, borderTop: `1px solid ${S.border}`, paddingTop: 14 }}>
            <div style={S.label}>COMPONENTS</div>
            {[["NetworkX", "DiGraph engine"], ["BFS / DFS", "Path traversal"], ["Adaptive", "Rule weights"], ["No ML", "Explainable rules"]].map(([k, v]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                <span style={{ fontSize: 10, color: S.accent }}>{k}</span>
                <span style={{ fontSize: 10, color: S.muted }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* MAIN PANEL */}
        <div style={{ flex: 1, overflowY: "auto", padding: "18px 22px" }}>

          {/* Tabs */}
          <div style={{ display: "flex", gap: 0, marginBottom: 18, borderBottom: `1px solid ${S.border}` }}>
            {["overview", "journey", "features", "feedback"].map((t) => (
              <button key={t} onClick={() => setTab(t)} style={{
                padding: "8px 18px", background: "none", border: "none",
                borderBottom: `2px solid ${tab === t ? S.accent : "transparent"}`,
                color: tab === t ? "#60a5fa" : S.muted,
                cursor: "pointer", fontSize: 11, letterSpacing: 3,
                fontFamily: "monospace", textTransform: "uppercase",
              }}>
                {t}
              </button>
            ))}
          </div>

          {/* ── OVERVIEW ── */}
          {tab === "overview" && (
            <div>
              {/* TX bar */}
              <div style={{ ...S.card, display: "flex", flexWrap: "wrap", gap: "10px 28px", marginBottom: 14 }}>
                {[["TX ID", txMeta.id], ["SOURCE", txMeta.from], ["DESTINATION", txMeta.to], ["AMOUNT", `Rs. ${txMeta.amount}`], ["CHANNEL", txMeta.channel], ["ACCOUNT AGE", `${txMeta.age} days`], ["COUNTRY", txMeta.country]].map(([lbl, val]) => (
                  <div key={lbl}>
                    <div style={{ fontSize: 8, color: S.muted, letterSpacing: 2, marginBottom: 3 }}>{lbl}</div>
                    <div style={{ fontSize: 12, color: S.text }}>{val}</div>
                  </div>
                ))}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "196px 1fr", gap: 14, marginBottom: 14 }}>
                {/* Gauge card */}
                <div style={{ ...S.card, display: "flex", flexDirection: "column", alignItems: "center" }}>
                  <GaugeArc score={score} />
                  <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: scoreColor(score) }} />
                    <span style={{ color: scoreColor(score), fontSize: 11, fontWeight: 700, letterSpacing: 2 }}>
                      {score < 40 ? "LOW" : score < 70 ? "MEDIUM" : score < 85 ? "HIGH" : "CRITICAL"}
                    </span>
                  </div>
                  <div style={{ marginTop: 14, width: "100%", borderTop: `1px solid ${S.border}`, paddingTop: 12 }}>
                    {[["0 – 39", "ALLOW", "#16a34a"], ["40 – 69", "MONITOR", "#b45309"], ["70 – 84", "STEP UP", "#dc2626"], ["85 +", "INTERCEPT", "#b91c1c"]].map(([r, l, c]) => (
                      <div key={r} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", fontSize: 9, borderBottom: `1px solid ${S.sub}` }}>
                        <span style={{ color: S.muted }}>{r}</span>
                        <span style={{ color: c }}>{l}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Decision + reasons */}
                <div>
                  <DecisionBadge
                    action={action}
                    message={scenario === "attack" ? atk.message : "Transaction processed. No adverse signals detected within the 30-minute behavioral window."}
                  />
                  <div style={S.card}>
                    <div style={S.label}>RISK SIGNALS</div>
                    {reasons.map((r, i) => {
                      const hi = r.includes("ATM") || r.includes("cashout") || r.includes("hop") || r.includes("Channel");
                      return (
                        <div key={i} style={{ display: "flex", gap: 10, marginBottom: 9, alignItems: "flex-start" }}>
                          <div style={{ width: 2, background: hi ? "#dc2626" : S.border2, alignSelf: "stretch", minHeight: 14, marginTop: 2, flexShrink: 0 }} />
                          <span style={{ fontSize: 12, color: "#4b5563", lineHeight: 1.55 }}>{r}</span>
                        </div>
                      );
                    })}
                  </div>

                  {scenario === "attack" && attackStep === 3 && (
                    <div style={{ marginTop: 12, background: "#140000", border: "1px solid #7f1d1d", borderRadius: 5, padding: "12px 16px" }}>
                      <div style={{ fontSize: 11, color: "#f87171", fontWeight: 700, letterSpacing: 1, marginBottom: 6 }}>EXIT-POINT INTERCEPTION ACTIVE</div>
                      <div style={{ fontSize: 11, color: "#4b5563", lineHeight: 1.65 }}>
                        ATM withdrawal re-evaluated at irreversible boundary. 3-hop cashout path confirmed by BFS traversal. Funds frozen pending analyst review.
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Score bar chart */}
              {scenario === "attack" && (
                <div style={S.card}>
                  <div style={S.label}>RISK SCORE EVOLUTION — MULE CHAIN</div>
                  <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height: 110 }}>
                    {ATTACK_CHAIN.map((step, i) => {
                      const h      = (step.score / 100) * 90;
                      const active = i === attackStep;
                      const faded  = i > attackStep;
                      const col    = scoreColor(step.score);
                      return (
                        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 5, opacity: faded ? 0.15 : 1, transition: "opacity 0.3s" }}>
                          <span style={{ fontSize: 11, color: col, fontWeight: active ? 700 : 400 }}>
                            {i <= attackStep ? step.score.toFixed(1) : "—"}
                          </span>
                          <div style={{ width: "100%", height: `${h}px`, background: faded ? S.border2 : col + (active ? "ff" : "99"), borderRadius: "2px 2px 0 0", transition: "height 0.5s ease" }} />
                          <span style={{ fontSize: 9, color: S.muted }}>ATK {i + 1}</span>
                          <span style={{ fontSize: 9, color: ACTION_META[step.action]?.color || S.text }}>
                            {i <= attackStep ? step.action.split("_")[0] : "—"}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── JOURNEY ── */}
          {tab === "journey" && (
            <div>
              <div style={{ ...S.card, marginBottom: 14 }}>
                <div style={S.label}>TEMPORAL BFS PATHS — 30-MIN WINDOW / MAX 3 HOPS</div>
                {scenario === "attack" && atk.paths.length > 0
                  ? <PathViz paths={atk.paths} />
                  : <p style={{ color: S.muted, fontSize: 12, margin: 0, lineHeight: 1.7 }}>
                      {scenario === "normal"   && "Single-hop transfer. No suspicious chain detected within the 30-minute temporal window. Account age and country within normal parameters."}
                      {scenario === "business" && "Direct business-to-vendor payment. One-hop path. Consistent with normal commercial account behavior."}
                      {scenario === "attack"   && "No multi-hop paths detected yet. Inject the next transaction to extend the chain."}
                    </p>
                }
              </div>

              {scenario === "attack" && attackStep >= 1 && (
                <div style={S.card}>
                  <div style={S.label}>CHAIN TIMELINE</div>
                  {ATTACK_CHAIN.slice(0, attackStep + 1).map((step, i) => {
                    const col = ACTION_META[step.action]?.color || S.text;
                    return (
                      <div key={i} style={{ display: "flex", gap: 14, marginBottom: 14 }}>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
                          <div style={{ width: 26, height: 26, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, background: `${col}14`, border: `1px solid ${col}`, color: col }}>
                            {i + 1}
                          </div>
                          {i < attackStep && <div style={{ width: 1, height: 16, background: S.border, marginTop: 4 }} />}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                            <span style={{ fontSize: 12, color: S.text }}>{step.tx.source} → {step.tx.destination}</span>
                            <span style={{ fontSize: 11, color: col, letterSpacing: 1 }}>{step.action.replace(/_/g, " ")}</span>
                          </div>
                          <div style={{ fontSize: 10, color: S.muted }}>
                            {step.tx.channel} · Rs.{step.tx.amount.toLocaleString()} · {step.tx.timestamp.slice(11, 16)} UTC · Score {step.score}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ── FEATURES ── */}
          {tab === "features" && (
            <div>
              <div style={{ ...S.card, marginBottom: 14 }}>
                <div style={S.label}>FEATURE SCORE BREAKDOWN</div>
                {Object.entries(features).map(([k, v]) => (
                  <FeatureBar key={k} label={FEATURE_LABELS[k] || k} value={v} weight={WEIGHTS_BEFORE[k] || 0} />
                ))}
              </div>
              <div style={S.card}>
                <div style={S.label}>FEATURE DEFINITIONS</div>
                {[
                  ["Velocity Score",       "Transaction count and total amount moved within the 30-minute behavioral window."],
                  ["Hop Score",            "Maximum hops across all BFS paths. 3 hops = 0.9. Time compression adds +0.2."],
                  ["Channel Switch Score", "Channel changes across the traversal path. Each switch adds 0.35. ATM cashout adds 0.4."],
                  ["New Account Penalty",  "Account age weighting. Under 7 days = 1.0. Under 30 = 0.85. Under 90 = 0.4."],
                  ["Cross-Border Penalty", "Source country risk tier. High-risk jurisdictions score 1.0. Multi-country path adds 0.3."],
                  ["Amount Concentration", "Ratio of this transaction to the window total. High concentration signals irregular flow."],
                ].map(([label, def]) => (
                  <div key={label} style={{ marginBottom: 11, paddingBottom: 11, borderBottom: `1px solid ${S.sub}` }}>
                    <div style={{ fontSize: 11, color: "#3b82f6", marginBottom: 4 }}>{label}</div>
                    <div style={{ fontSize: 11, color: "#4b5563", lineHeight: 1.6 }}>{def}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── FEEDBACK ── */}
          {tab === "feedback" && (
            <div>
              <div style={{ ...S.card, marginBottom: 14 }}>
                <div style={S.label}>CLOSED-LOOP ANALYST FEEDBACK</div>
                <p style={{ fontSize: 12, color: "#4b5563", lineHeight: 1.8, margin: "0 0 16px" }}>
                  When an analyst confirms fraud or marks a false positive, contributing feature weights adjust by a fixed learning rate (5%) and renormalize. The system adapts without ML retraining cycles.
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div style={{ background: "#052e16", border: "1px solid #166534", borderRadius: 4, padding: 14 }}>
                    <div style={{ color: "#4ade80", fontSize: 11, fontWeight: 700, letterSpacing: 2, marginBottom: 8 }}>CONFIRM FRAUD</div>
                    <div style={{ color: "#4b5563", fontSize: 11, lineHeight: 1.65 }}>Contributing weights increase +5%, then renormalize. Scrutiny boost applied to 1-hop neighbors for 60 minutes.</div>
                  </div>
                  <div style={{ background: "#1a1040", border: "1px solid #3730a3", borderRadius: 4, padding: 14 }}>
                    <div style={{ color: "#818cf8", fontSize: 11, fontWeight: 700, letterSpacing: 2, marginBottom: 8 }}>FALSE POSITIVE</div>
                    <div style={{ color: "#4b5563", fontSize: 11, lineHeight: 1.65 }}>Over-contributing weights decrease −5%, then renormalize. Reduces unnecessary step-up triggers over time.</div>
                  </div>
                </div>
              </div>

              {feedbackDone ? (
                <>
                  <WeightCompare before={WEIGHTS_BEFORE} after={WEIGHTS_AFTER} />
                  <div style={{ ...S.card, marginTop: 14 }}>
                    <div style={S.label}>NEIGHBOR SCRUTINY PROPAGATION</div>
                    <p style={{ fontSize: 12, color: "#4b5563", margin: "0 0 12px", lineHeight: 1.7 }}>
                      2 accounts within 1 hop of MULE_2668 placed under enhanced scrutiny. Risk score boosted by +8 points for 60 minutes. Prevents chain continuation through adjacent accounts.
                    </p>
                    <div style={{ display: "flex", gap: 8 }}>
                      {["MULE_40A3", "ATM_F912"].map((acc) => (
                        <div key={acc} style={{ padding: "4px 12px", background: "#1c1000", border: "1px solid #78350f", borderRadius: 3, fontSize: 11, color: "#b45309", fontFamily: "monospace" }}>
                          {acc}
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div style={S.card}>
                  <p style={{ fontSize: 11, color: S.muted, margin: "0 0 16px" }}>
                    {scenario !== "attack"
                      ? "Select the Mule Attack scenario and click ANALYST CONFIRM after completing the chain to view adaptive weight updates."
                      : attackStep < 3
                      ? "Inject all 4 transactions to complete the chain, then confirm fraud to view weight adaptation."
                      : "Click ANALYST CONFIRM in the left panel to apply feedback and view the weight delta table."}
                  </p>
                  <WeightCompare before={WEIGHTS_BEFORE} after={WEIGHTS_BEFORE} />
                </div>
              )}
            </div>
          )}
        </div>

        {/* RIGHT SIDEBAR */}
        <div style={{ width: 208, borderLeft: `1px solid ${S.border}`, padding: "18px 14px", overflowY: "auto", background: "#030b16", flexShrink: 0 }}>

          <div style={S.label}>DECISION THRESHOLDS</div>
          {[
            ["0 – 39",  "ALLOW",     "#16a34a", "Low risk. Pass through."],
            ["40 – 69", "MONITOR",   "#b45309", "Elevated. Log and watch."],
            ["70 – 84", "STEP UP",   "#dc2626", "High. Auth required."],
            ["85 +",    "INTERCEPT", "#b91c1c", "Critical. Block."],
          ].map(([range, lbl, col, desc]) => (
            <div key={range} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: `1px solid ${S.sub}` }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 9, color: S.muted }}>{range}</span>
                <span style={{ fontSize: 10, color: col, fontWeight: 700 }}>{lbl}</span>
              </div>
              <div style={{ fontSize: 9, color: S.sub }}>{desc}</div>
            </div>
          ))}

          <div style={{ marginTop: 8 }}>
            <div style={S.label}>EXIT-POINT LOGIC</div>
            <div style={{ fontSize: 10, color: S.sub, lineHeight: 1.85 }}>
              When channel = ATM or EXTERNAL_TRANSFER, a secondary evaluation runs regardless of base score.
              <br /><br />
              Cashout + score 65 or above triggers INTERCEPT.
              <br /><br />
              Score 70 on high-value transfers triggers DELAY.
            </div>
          </div>

          <div style={{ marginTop: 20, borderTop: `1px solid ${S.border}`, paddingTop: 14 }}>
            <div style={S.label}>POSITIONING</div>
            <div style={{ fontSize: 9, color: "#1d3a6e", lineHeight: 1.9 }}>
              Event-driven temporal subgraph traversal for real-time operational decisioning at irreversible transaction boundaries.
            </div>
          </div>
        </div>

      </div>

      <style>{`
        * { box-sizing: border-box; }
        button { transition: opacity 0.15s; }
        button:hover { opacity: 0.8; }
        ::-webkit-scrollbar { width: 3px; }
        ::-webkit-scrollbar-track { background: #020810; }
        ::-webkit-scrollbar-thumb { background: #0f1a2e; border-radius: 2px; }
      `}</style>
    </div>
  );
}
