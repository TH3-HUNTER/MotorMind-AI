# ⚙ FactoryGuard AI — UiPath AgentHack 2026

**Real-time predictive maintenance agent for industrial motors, orchestrated by UiPath Maestro BPMN**

Track: **UiPath Maestro BPMN (Track 2)**
Developer: **Hamza Manai** — Electrical Engineering / Industry 4.0, Tunisia

---

## The Problem

Industrial motor failures cost factories thousands of dollars per hour in unplanned downtime. Existing monitoring systems display values and alarms — but they don't explain *why* a fault happened, *what to do next*, or *who needs to approve the action*. Engineers lose time diagnosing problems that an AI agent could solve in seconds.

## The Solution

FactoryGuard AI is a **multi-agent BPMN-orchestrated maintenance system** built on UiPath Maestro. It continuously monitors a 3-phase industrial motor, detects faults using a 23-rule physics-based engine, calls an AI diagnostic agent for root cause analysis, and routes the result through a governed BPMN process — notifying engineers, creating human approval tasks, and executing corrective actions automatically.

---

## BPMN Process Flow

```
[START: Motor Sensor Reading]
          ↓
[Coded Agent: Physics Simulation + 23-Rule Fault Engine]
          ↓
[AI Agent: Gemini Diagnosis → STATUS / ROOT CAUSE / ACTIONS / RISK]
          ↓
    [Decision: Severity?]
    ↓           ↓           ↓
[HEALTHY]  [WARNING]   [CRITICAL]
    ↓           ↓           ↓
[Log OK]  [Human Task: [Auto-Alert +
[Wait 60s] Engineer    Human Approval
           Reviews]    for Shutdown]
    ↓           ↓           ↓
         [Action Executed + Incident Logged]
                    ↓
                  [END]
```

---

## UiPath Components Used

| Component | How it's used |
|-----------|--------------|
| **UiPath Maestro BPMN** | Orchestrates the full motor monitoring process — agents, human tasks, decisions, and logging |
| **UiPath Agent Builder** | Hosts the FactoryGuard AI conversational agent — engineers can ask questions about motor health |
| **UiPath Coded Agent (Python SDK)** | Core motor physics engine + 23-rule fault detection + Gemini AI diagnosis |
| **UiPath Human Tasks** | Engineer review and approval workflow on WARNING/CRITICAL faults |
| **UiPath API Workflows** | Connects the coded agent to Maestro and external notification systems |

---

## Agent Type

This solution uses **both**:
- **Coded Agent** (Python) — the motor physics simulation, fault detection engine, and Gemini AI call
- **Low-code Agent** (UiPath Agent Builder) — the conversational interface for engineer Q&A

---

## Motor Physics Model

All sensor values are calculated from real electrical engineering equations — not random numbers.

| Sensor | Formula | Why it matters |
|--------|---------|---------------|
| Current | `I = P / (√3 × V × cosφ)` | Rises automatically when voltage drops |
| Temperature | `T = T_ambient + k × I²` | Joule heating — current causes heat |
| Vibration | ISO 10816 standard | Spikes characteristically on bearing fault |
| Power | `P = √3 × V × I × cosφ / 1000` kW | Full power balance |

**Motor specs:** 400V / 7.5kW / 1450 RPM / 15.2A rated / PF 0.85 / Class F insulation / 91% efficiency

---

## 23 Fault Detection Rules

| Category | Rules |
|----------|-------|
| Electrical | Low voltage, critical undervoltage, overvoltage, overcurrent, critical overcurrent, combined voltage+current |
| Thermal | High temperature, critical temperature, cooling failure, temperature trending |
| Mechanical | High vibration, critical vibration, RPM drop, vibration trending |
| Advanced | Slip anomaly, stall detection, phase imbalance proxy, efficiency degradation, power factor deviation, thermal sensor anomaly, current trending, overvoltage+overtemp combined, idle current draw |

---

## Fault Injection Scenarios

| Scenario | What the agent detects |
|----------|----------------------|
| Voltage drop to 310V | Overcurrent (+31%), winding overload risk, real physics: I = P/(√3·V·cosφ) |
| Bearing fault | Vibration >8 mm/s, RPM drop to 93%, thermal rise +12°C |
| Overtemperature | Cooling failure, insulation class F limit approaching |
| Overcurrent | 1.45× rated current, winding damage risk |
| Combined: voltage + bearing | Cascading failure chain, BPMN routes to emergency escalation |

---

## AI Diagnostic Output

Every diagnosis returns a structured 5-section report:

```
STATUS: CRITICAL — motor drawing 20.1A due to supply voltage drop to 312V.

OBSERVATIONS: Current is 20.1A, 32% above rated 15.2A. Supply voltage at 312V,
  22% below rated 400V, causing proportional overcurrent per I = P/(√3·V·cosφ).

ROOT CAUSE: Voltage drop forces higher current draw to maintain torque.
  At 312V, current must increase by factor V_rated/V_actual = 1.28 to
  deliver same shaft power. Winding I²R losses increase by 64%.

Action 1 IMMEDIATE: Check main distribution panel for loose connections
  or failed tap changer. Use clamp meter to verify three-phase balance.
Action 2 THIS WEEK: Install voltage stabilizer or UPS upstream of motor.
Action 3 NEXT MAINTENANCE: Check winding insulation resistance (megger test).

RISK ASSESSMENT: At current overload level, winding insulation will degrade
  within 4-8 hours of continuous operation. Immediate voltage restoration
  recommended. Safety risk: HIGH — overheating + potential winding failure.
```

---

## Setup Instructions

### Requirements
- Python 3.10+
- Gemini API key (free at [aistudio.google.com](https://aistudio.google.com))
- UiPath Automation Cloud account (Labs access for hackathon)

### Local run (test the agent)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/factoryguard-uipath.git
cd factoryguard-uipath

# Set your Gemini API key
export GEMINI_API_KEY=your_key_here   # Linux/Mac
set GEMINI_API_KEY=your_key_here      # Windows

# Run a single diagnosis (healthy motor)
python agent/motor_agent.py

# Simulate a bearing fault
python agent/motor_agent.py --simulate bearing

# Simulate voltage drop
python agent/motor_agent.py --simulate voltage

# Simulate combined fault (worst case)
python agent/motor_agent.py --simulate combined

# Start HTTP server mode (for UiPath Agent Builder)
python agent/motor_agent.py --serve
```

### Connect to UiPath

1. Start the agent in server mode: `python agent/motor_agent.py --serve`
2. In UiPath Agent Builder → New Agent → Webhook → point to `http://localhost:8080`
3. Import the BPMN process from `uipath/factoryguard_process.xaml`
4. Configure human task assignees in Maestro settings
5. Run the process — it will loop every 60 seconds

---

## AI-Assisted Development

This project was built with assistance from **Claude** (Anthropic) as a coding agent, used for:
- Architecture design and BPMN flow planning
- Python coded agent scaffolding and physics engine validation
- Prompt engineering for the Gemini diagnostic system
- Code review and debugging

Claude was used as a development tool throughout the build process. All motor physics, fault detection rules, and engineering domain knowledge are original work based on the developer's electrical engineering background.

*Per UiPath AgentHack rules, use of AI coding assistants is permitted and eligible for bonus points when documented.*

---

## Project Structure

```
factoryguard-uipath/
├── agent/
│   └── motor_agent.py          ← Python coded agent (core logic)
├── uipath/
│   └── factoryguard_process.xaml ← Maestro BPMN process definition
├── docs/
│   └── architecture.png        ← Architecture diagram
├── README.md                   ← This file
├── requirements.txt
└── LICENSE                     ← MIT
```

---

## About the Developer

**Hamza Manai** — Electrical Engineering graduate, Industry 4.0 Master's student, Tunisia.
Domain expertise: predictive maintenance, resistance welding machines, 3-phase motor protection systems.

GitHub: [https://github.com/TH3-HUNTER](https://github.com/TH3-HUNTER)
