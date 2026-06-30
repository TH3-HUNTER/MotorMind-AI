# MotorMind AI

**Real-time predictive maintenance for 3-phase industrial motors, orchestrated by UiPath Maestro BPMN.**

UiPath AgentHack 2026 — Track 2: Maestro BPMN
Built by Hamza Manai — Electrical Engineering / Mechatronics

[Live Demo](http://8.216.39.121:5000) · Built with Claude (Anthropic) as a coding assistant throughout development

---

## Project Description

### The Problem

3-phase induction motors power roughly 70% of all industrial processes worldwide. A single unplanned motor failure costs $50,000–$260,000 per hour in lost production. Traditional monitoring systems only alarm **after** the failure has already occurred — by then it's too late to prevent downtime.

Motors give early warning signals 30–90 minutes before catastrophic failure: voltage drops, temperature rises, vibration anomalies. No human can monitor six sensor channels simultaneously, 24/7. And without governance, there's no guarantee the right engineer gets the right information at the right time.

### What MotorMind AI Does

MotorMind AI is a real-time predictive maintenance agent that:

1. **Simulates a real 3-phase motor** (400V / 7.5kW / 1450 RPM) using actual electrical engineering equations — not random noise. Voltage drop genuinely causes current rise, current rise genuinely causes I²R heating, exactly like a real motor.

2. **Detects faults using 23 physics-based rules** compliant with **IEC 60038** (voltage standard) and **ISO 10816-3** (vibration severity zones) — the same standards used in real industrial maintenance.

3. **Diagnoses root causes with Gemini AI**, reasoning like a senior electrical engineer: STATUS → OBSERVATIONS → ROOT CAUSE → RECOMMENDED ACTIONS → RISK ASSESSMENT.

4. **Orchestrates the full response through UiPath Maestro BPMN** — fetching live sensor data, running AI diagnosis, and routing the outcome through an Exclusive Gateway: HEALTHY logs automatically, WARNING triggers an engineer review, CRITICAL requires human approval before any shutdown action.

5. **Provides a live web dashboard** with motor start/stop/emergency-shutdown controls (with realistic ramp-up and ramp-down physics), 0.5-second sensor updates, live trend visualization, AI diagnosis output, and a real-time log of every message UiPath sends back.

The result is a governed, auditable predictive maintenance pipeline — not just a dashboard that shows information, but a system that routes decisions to the right person and records every step.

---

## UiPath Components Used

| Component | Role in MotorMind AI |
|---|---|
| **UiPath Maestro BPMN** | Core orchestration layer. Models the full process: Fetch Motor Data → MotorMind Diagnosis Agent → Check Fault Severity (Exclusive Gateway) → route to Log / Engineer Review / Emergency Alert → 30-second loop back |
| **UiPath Agent Builder** | Defines the MotorMind Diagnosis Agent — receives 7 sensor inputs (voltage_v, current_a, temperature_c, vibration_mm_s, rpm, status, faults), runs the configured LLM, returns structured `severity` and `diagnosis` outputs consumed by the BPMN gateway |
| **HTTP / Web API Connector** | Used inside a Send Task to call our external Flask API (`/api/latest`, `/api/diagnose`, `/api/uipath/human-task`) hosted on Alibaba Cloud — the bridge between UiPath and the Python physics/AI engine |
| **Studio Web (Solution Explorer)** | Used to build, debug, and manage the Agent, the Maestro BPMN process, and the SimpleApprovalApp together as a single solution |
| **Orchestrator** | Deployment target for the published solution; execution trail, step variables, and job history were used throughout development to debug the agent and the BPMN flow |
| **UiPath Action Apps (SimpleApprovalApp)** | Built and configured (ActionSchema, outcomes: Approve/Reject, input properties for diagnosis and severity) for human task review — see *Known Limitations* below regarding Action Center availability on the hackathon tenant |

---

## Agent Type

**This solution uses a Low-Code Agent (UiPath Agent Builder), combined with an external Coded Agent (Python + Gemini) called via HTTP.**

Specifically:

- The **MotorMind Diagnosis Agent** is a **Low-Code Agent** built in UiPath Agent Builder, with a defined system prompt, user prompt, I/O schema (7 typed inputs, 2 typed outputs), and model configuration.
- The **physics simulation and 23-rule fault engine** is a **Coded Agent** — a custom Python application (`motor_agent.py`) implementing real motor equations and IEC 60038 / ISO 10816 compliant thresholds, deployed independently and exposed via a public REST API.
- These two agents are connected through UiPath's HTTP/Web API connector, demonstrating the hybrid architecture the hackathon explicitly encourages: *"bring in agents built on external frameworks."* UiPath is the orchestration and governance layer; the external Python agent is the domain-specific physics/AI engine it calls.

---

## Architecture

```
┌─────────────────────────┐
│   Motor Simulator        │   6 sensors, updated every 1s
│   (Python physics model) │
└───────────┬──────────────┘
            │
┌───────────▼──────────────┐
│  Flask App + 23-Rule       │   IEC 60038 / ISO 10816 compliant
│  Fault Engine (Coded Agent)│   fault detection
│  Deployed on Alibaba Cloud │
│  (public, always online)   │
└───────────┬──────────────┘
            │ HTTP GET /api/latest
            │ HTTP POST /api/diagnose
┌───────────▼──────────────┐
│   UiPath Maestro BPMN      │
│                             │
│  Start                      │
│   → Fetch Motor Data (Send) │
│   → MotorMind Diagnosis     │
│     Agent (Low-Code Agent)  │
│   → Check Fault Severity    │
│     (Exclusive Gateway)     │
│       → HEALTHY → Log       │
│       → WARNING → Review    │
│       → CRITICAL → Approve  │
│   → 30s timer → loop back   │
└─────────────────────────────┘
```

---

## Motor Physics Model

All sensor values are calculated from real electrical engineering equations — not random numbers.

| Sensor | Formula | Why it matters |
|---|---|---|
| Current | I = P / (√3 × V × cosφ) | Rises automatically when voltage drops |
| Temperature | T = T_ambient + k × I² | Joule heating — current causes heat |
| Vibration | ISO 10816 standard | Spikes characteristically on bearing fault |
| Power | P = √3 × V × I × cosφ / 1000 (kW) | Full power balance |

**Motor specs:** 400V / 7.5kW / 1450 RPM / 15.2A rated / PF 0.85 / Class F insulation / 91% efficiency

---

## 23 Fault Detection Rules

| Category | Rules |
|---|---|
| **Electrical** | Low voltage, critical undervoltage, overvoltage, overcurrent, critical overcurrent, combined voltage+current |
| **Thermal** | High temperature, critical temperature, cooling failure, temperature trending |
| **Mechanical** | High vibration, critical vibration, RPM drop, vibration trending |
| **Advanced** | Slip anomaly, stall detection, phase imbalance proxy, efficiency degradation, power factor deviation, thermal sensor anomaly, current trending, overvoltage+overtemp combined, idle current draw |

---

## Fault Injection Scenarios

| Scenario | What the agent detects |
|---|---|
| Voltage drop to 310–320V | Overcurrent (+30–41%), winding overload risk, real physics: I = P/(√3·V·cosφ) |
| Bearing fault | Vibration >7–8 mm/s, RPM drop, thermal rise from friction |
| Overtemperature | Cooling failure detection, insulation Class F limit approaching |
| Overcurrent | Up to 1.45× rated current, winding damage risk |
| Combined: voltage + bearing | Cascading failure chain — BPMN routes to emergency escalation |

---

## Example AI Diagnostic Output

```
STATUS: CRITICAL — motor drawing 21.5A due to supply voltage drop to 320V.

OBSERVATIONS: Current is 21.5A, 41% above rated 15.2A. Supply voltage at 320V,
  20% below rated 400V, causing proportional overcurrent per I = P/(√3·V·cosφ).

ROOT CAUSE: Voltage drop forces higher current draw to maintain torque. At 320V,
  current must increase to deliver the same shaft power. Winding I²R losses
  rise sharply, pushing temperature toward the Class F insulation limit (155°C).

ACTION 1 [IMMEDIATE]: Measure all 3 phase voltages at the motor terminal box
  with a calibrated multimeter. Check distribution panel for loose connections.
ACTION 2 [THIS WEEK]: Install a voltage stabilizer or UPS upstream of the motor.
ACTION 3 [NEXT MAINTENANCE]: Megger-test winding insulation resistance.

RISK ASSESSMENT: Insulation failure within 2–4 hours of continuous operation.
  Immediate shutdown recommended. Personnel safety risk: MEDIUM (arc flash).
```

### 1. Try the live system (fastest — no installation)

1. Open **http://8.216.39.121:5000** in any browser. This is the live Flask dashboard, deployed on a public Alibaba Cloud server (Ubuntu 22.04), online 24/7 for judging.
2. Click **Start** — the motor ramps up over a 4-second startup sequence.
3. Use the sidebar sliders (Load, Supply Voltage, RPM Setpoint) and fault-injection buttons (Bearing, Overtemp, Volt Drop, Overcurrent) to create different motor conditions.
4. Click **Run Diagnosis** to trigger a Gemini AI analysis, or wait — it runs automatically every 30 seconds while the motor is running.
5. Inject a fault (e.g., **Bearing**) and watch the status card change to WARNING/CRITICAL with a full structured diagnosis (STATUS / OBSERVATIONS / ROOT CAUSE / ACTIONS / RISK).
6. The **UiPath Messages** panel in the sidebar shows live messages received from the UiPath Maestro BPMN process when it runs (see below).

### 2. Run the UiPath Maestro BPMN process

1. Sign in to **cloud.uipath.com**, tenant: `motormindai`.
2. Open **Solution → Maestro BPMN → Process.bpmn**.
3. Click **Debug** (see *Known Limitations* — Publish is currently broken on this tenant's Community Plan; Debug deploys and runs the process correctly).
4. The process will:
   - Call `GET http://8.216.39.121:5000/api/latest` to fetch live sensor data
   - Pass it to the **MotorMind Diagnosis Agent**
   - Route through the **Check Fault Severity** gateway based on the returned `severity`
   - Log the result / notify for review / request shutdown approval accordingly
5. Open the **Execution Trail** tab to see every step (Fetch Motor Data → Agent run → LLM call → Agent output → Gateway → routed task), each with full input/output JSON visible under **Step variables**.

### 3. Run the Python backend locally (optional, for code review)

```bash
git clone https://github.com/TH3-HUNTER/MotorMind-AI.git
cd MotorMind-AI
pip install flask gunicorn
python web_app.py
# Open http://localhost:5000
```

To point your own UiPath BPMN at a local instance instead of the Alibaba Cloud deployment, replace the URL in the **Fetch Motor Data** Send Task with `http://YOUR_IP:5000/api/latest`.

### 4. Environment / configuration

- Gemini API key is already configured in `motor_agent.py` and `web_app.py` for judging convenience (free tier). No additional setup required.
- No `.env` file or secrets management needed to run the demo.

---

## Known Limitations & Platform Issues Encountered

In the interest of transparency, the following platform-level issues affected development and are reflected in the current state of the submission:

- **Maestro BPMN Publish is broken** on the hackathon Community Plan tenant — every Publish attempt returns *"No solution tool factory is registered."* The Debug button initially showed the same error; debugging this further confirmed it was a platform-side issue, not a configuration problem. We have not found a workaround and are waiting on the UiPath team to resolve it. **Debug currently works and is the recommended way for judges to run the process end-to-end.**
- **GPT-5.4 AI Units were exhausted (250/250)** during development. We did not change the underlying model. Instead, we modified the main BPMN process to bypass the Agent step during testing (calling the Flask `/api/diagnose` endpoint directly, which uses Gemini) so that development could continue while waiting for the unit quota to reset.
- **UiPath Action Center / Action Apps are not enabled** on this hackathon tenant ("Actions requires UiPath Automation Cloud"). The `SimpleApprovalApp` (Action Schema, outcomes, input properties) was fully built and is included in the solution, but cannot be triggered as a live human task on this tenant. As a working alternative, WARNING/CRITICAL events are sent via HTTP POST to our Flask API and displayed in real time in the dashboard's **UiPath Messages** panel, simulating the same human-in-the-loop notification flow.
- **Studio Desktop could not be used** as a fallback (Error 1232 — no robot license assigned on the Community Plan tenant). Development was done entirely in Studio Web.

A full writeup of these issues, what was tried, and the workarounds used is included in the project's Devpost submission and presentation.

---

## Standards & Engineering References

- **IEC 60038** — voltage thresholds: ±5% warning band (380–420V), ±10% critical band (360–440V)
- **ISO 10816-3** — vibration severity: Zone B/C boundary at 4.5 mm/s, Zone D (critical) at 7.1 mm/s
- **IEC 60034** — insulation classes referenced in AI risk assessment (Class F = 155°C limit)

---

## Tech Stack

`Python` · `Flask` · `Gunicorn` · `Gemini AI` (gemini-3.1-flash-lite) · `UiPath Studio Web` · `UiPath Maestro BPMN` · `UiPath Agent Builder` · `Alibaba Cloud ECS (Ubuntu 22.04)` · vanilla `JavaScript` / `CSS`

---

## Acknowledgements — AI-Assisted Development

This project was built with assistance from **Claude (Anthropic)**, used as a coding agent throughout development for:

- Architecture design and BPMN flow planning
- Python coded agent scaffolding and motor physics equation validation
- Flask backend development, debugging, and deployment (Alibaba Cloud)
- UiPath BPMN/XML troubleshooting (variable binding, gateway conditions, Send Task configuration)
- Prompt engineering for the Gemini diagnostic agent's system/user prompts
- Code review, bug fixing, and this documentation

Claude was used as a development tool throughout the build process. All motor physics, fault detection rules, electrical engineering standards (IEC 60038, ISO 10816, IEC 60034), and domain knowledge are original work based on the developer's Electrical Engineering background and hands-on industrial experience.

*Per UiPath AgentHack rules, use of AI coding assistants is permitted and eligible for bonus points when documented — hence this section.*

---

## Project Structure

```
MotorMind-AI/
├── web_app.py                  ← Flask web dashboard (main entry point)
├── agent/
│   └── motor_agent.py          ← Coded agent: physics engine + 23-rule fault
│                                   detection + Gemini AI diagnosis + Flask
│                                   server mode for UiPath HTTP calls
├── docs/
│   └── architecture.png        ← Architecture diagram
├── requirements.txt
├── README.md                   ← This file
└── LICENSE
```

---

## About the Developer

**Hamza Manai** — Electrical Engineering graduate, Mechatronics Master's student (ISET Radès, Tunisia). Domain expertise: predictive maintenance, resistance welding machine diagnostics (PFE project with ESP32 + AI fault prediction), 3-phase motor protection systems, industrial automation (TIA Portal, PID control).

GitHub: https://github.com/TH3-HUNTER

---

## Links

- **Live Demo:** http://8.216.39.121:5000
- **UiPath Orchestrator:** cloud.uipath.com/motormindai
- **Author:** Hamza Manai — manaihamza2003@gmail.com
