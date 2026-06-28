"""
MotorMind AI — UiPath Coded Agent
Motor: 400V / 7.5kW / 1450 RPM 3-phase induction motor
"""

import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL          = "gemini-3.1-flash-lite"
GEMINI_URL     = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# Motor rated values — 400V 7.5kW 3-phase induction motor
V_RATED   = 400.0
I_RATED   = 15.2
RPM_RATED = 1450
P_RATED   = 7500    # watts
T_AMBIENT = 25.0
T_RATED   = 75.0    # at full load
PF        = 0.85
EFFICIENCY = 0.91

# Fault thresholds — IEC 60038 voltage, ISO 10816 vibration
THRESHOLDS = {
    "volt_warn_low":  380,   # IEC 60038: -5% of 400V
    "volt_warn_high": 420,   # IEC 60038: +5% of 400V
    "volt_crit_low":  360,   # IEC 60038: -10% of 400V
    "volt_crit_high": 440,   # IEC 60038: +10% of 400V
    "curr_warn":      17,
    "curr_crit":      22,
    "temp_warn":      80,
    "temp_crit":      100,
    "vib_warn":       4.5,   # ISO 10816-3 Zone B/C boundary
    "vib_crit":       7.1,   # ISO 10816-3 Zone D boundary
}


# ─── MOTOR PHYSICS ENGINE ─────────────────────────────────────────────────────
def simulate_motor(
    load_pct: float = 70.0,
    voltage_v: float = 400.0,
    rpm_setpoint: float = 1450.0,
    fault_bearing: bool = False,
    fault_overtemp: bool = False,
    fault_overcurrent: bool = False,
    fault_voltage_drop: bool = False,
    noise: bool = True,
) -> dict:
    """
    Simulate one motor reading using real electrical engineering equations.
    Returns a dict of sensor readings + status.
    """
    load = load_pct / 100.0

    # Voltage drop fault modifier
    if fault_voltage_drop:
        voltage_v = voltage_v * 0.78 + (random.uniform(-4, 4) if noise else 0)

    # RPM — slip increases with load; bearing fault reduces by 7%
    slip = 0.05 * load
    rpm = rpm_setpoint * (1.0 - slip)
    if fault_bearing:
        rpm *= 0.93
    if noise:
        rpm += random.uniform(-6, 6)
    rpm = max(0, rpm)

    # Current — from power balance (I = P / √3·V·cosφ)
    shaft_power = P_RATED * load * (rpm_setpoint / RPM_RATED) if rpm_setpoint > 0 else 0
    elec_power  = shaft_power / EFFICIENCY
    denom       = math.sqrt(3) * max(voltage_v, 1) * PF
    current     = elec_power / denom
    # Voltage drop causes proportional overcurrent (real motor physics)
    current *= (V_RATED / max(voltage_v, 1))
    if fault_overcurrent:
        current *= 1.45
    if noise:
        current += random.uniform(-0.2, 0.2)
    current = max(0, current)

    # Temperature — Joule heating model: T = T_ambient + k·I²
    k_thermal = (T_RATED - T_AMBIENT) / (I_RATED ** 2)
    temp = T_AMBIENT + k_thermal * (current ** 2)
    if fault_overtemp:
        temp += 35 + (random.uniform(0, 8) if noise else 0)
    if fault_bearing:
        temp += 12 + (random.uniform(0, 4) if noise else 0)
    if noise:
        temp += random.uniform(-0.4, 0.4)
    temp = max(T_AMBIENT, temp)

    # Vibration — mechanical + load component (ISO 10816)
    vib = 0.5 + 1.8 * load
    if fault_bearing:
        vib += 8.5 + (random.uniform(0, 2.5) if noise else 0)
        vib += 1.8 * math.sin(time.time() * 3.2)
    if voltage_v < 360:
        vib += (360 - voltage_v) / 60
    if noise:
        vib += random.uniform(-0.08, 0.08)
    vib = max(0.1, vib)

    # Power (kW)
    power_kw = (math.sqrt(3) * voltage_v * current * PF) / 1000

    # Status — priority order (IEC 60038 voltage thresholds)
    status = "HEALTHY"
    if fault_overcurrent or current > THRESHOLDS["curr_crit"]:
        status = "CRITICAL_OVERCURRENT"
    elif fault_overtemp or temp > THRESHOLDS["temp_crit"]:
        status = "CRITICAL_OVERTEMPERATURE"
    elif fault_bearing or vib > THRESHOLDS["vib_crit"]:
        status = "WARNING_BEARING_FAULT"
    elif voltage_v < THRESHOLDS["volt_crit_low"] or voltage_v > THRESHOLDS["volt_crit_high"]:
        status = "CRITICAL_VOLTAGE"
    elif voltage_v < THRESHOLDS["volt_warn_low"] or voltage_v > THRESHOLDS["volt_warn_high"]:
        status = "WARNING_VOLTAGE"    
    elif temp > THRESHOLDS["temp_warn"]:
        status = "WARNING_HIGH_TEMP"
    elif current > THRESHOLDS["curr_warn"]:
        status = "WARNING_HIGH_CURRENT"
    elif vib > THRESHOLDS["vib_warn"]:
        status = "WARNING_HIGH_VIBRATION"
    elif rpm_setpoint < 50:
        status = "IDLE"

    return {
        "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rpm":            round(rpm, 1),
        "temperature_c":  round(temp, 1),
        "vibration_mm_s": round(vib, 3),
        "current_a":      round(current, 2),
        "voltage_v":      round(voltage_v, 1),
        "power_kw":       round(power_kw, 3),
        "status":         status,
        "load_pct":       load_pct,
    }


# ─── 23-RULE FAULT DETECTION ENGINE ──────────────────────────────────────────
def detect_faults(readings: list[dict]) -> list[str]:
    """
    Run 23 engineering rules on a list of motor readings.
    Returns list of fault descriptions.
    """
    if not readings or len(readings) < 3:
        return []

    latest = readings[-1]
    volt   = float(latest.get("voltage_v", 400))
    curr   = float(latest.get("current_a", 0))
    temp   = float(latest.get("temperature_c", 25))
    vib    = float(latest.get("vibration_mm_s", 0))
    rpm    = float(latest.get("rpm", 0))

    temps = [float(r.get("temperature_c", 25)) for r in readings]
    vibs  = [float(r.get("vibration_mm_s", 0))  for r in readings]
    rpms  = [float(r.get("rpm", 0))              for r in readings]
    currs = [float(r.get("current_a", 0))        for r in readings]

    faults = []

    # ── Electrical rules (IEC 60038) ──────────────────────────────────────────
    # Rule 1 — undervoltage warning (-5%)
    if volt < THRESHOLDS["volt_warn_low"]:
        faults.append(f"LOW VOLTAGE {volt:.0f}V (IEC 60038: rated {V_RATED:.0f}V ±5%, limit 380V, -{((V_RATED-volt)/V_RATED*100):.1f}%)")
    # Rule 2 — undervoltage critical (-10%)
    if volt < THRESHOLDS["volt_crit_low"]:
        faults.append(f"CRITICAL UNDERVOLTAGE {volt:.0f}V (IEC 60038 -10% limit 360V) — winding damage risk")
    # Rule 3 — overvoltage warning (+5%)
    if volt > THRESHOLDS["volt_warn_high"]:
        faults.append(f"HIGH VOLTAGE {volt:.0f}V (IEC 60038: rated {V_RATED:.0f}V ±5%, limit 420V, +{((volt-V_RATED)/V_RATED*100):.1f}%)")
    # Rule 3b — overvoltage critical (+10%)
    if volt > THRESHOLDS["volt_crit_high"]:
        faults.append(f"CRITICAL OVERVOLTAGE {volt:.0f}V (IEC 60038 +10% limit 440V) — insulation failure risk")
    # Rule 4
    if curr > 18:
        faults.append(f"OVERCURRENT {curr:.1f}A (rated {I_RATED}A, "
                       f"+{((curr-I_RATED)/I_RATED*100):.0f}%)")
    # Rule 5
    if curr > 22:
        faults.append(f"CRITICAL OVERCURRENT {curr:.1f}A — immediate shutdown risk")
    # Rule 6 — combined
    if volt < 370 and curr > 16:
        faults.append(f"VOLTAGE DROP + OVERCURRENT V={volt:.0f}V I={curr:.1f}A — cascading fault")

    # ── Thermal rules ─────────────────────────────────────────────────────────
    # Rule 7
    if temp > 80:
        faults.append(f"HIGH TEMPERATURE {temp:.1f}C (limit 80C, class F insulation)")
    # Rule 8
    if temp > 100:
        faults.append(f"CRITICAL TEMPERATURE {temp:.1f}C — insulation failure imminent")
    # Rule 9 — cooling failure (temp higher than expected from current)
    exp_t = T_AMBIENT + ((T_RATED - T_AMBIENT) / (I_RATED ** 2)) * (curr ** 2)
    if temp > exp_t + 20:
        faults.append(f"COOLING FAILURE: {temp:.1f}C vs expected {exp_t:.0f}C "
                       f"(+{temp-exp_t:.0f}C excess)")
    # Rule 10 — temperature trending
    if len(temps) >= 10 and temps[-1] - temps[0] > 8:
        faults.append(f"TEMPERATURE RISING +{temps[-1]-temps[0]:.1f}C "
                       f"in {len(temps)}s — thermal runaway risk")

    # ── Mechanical rules ──────────────────────────────────────────────────────
    # Rule 11
    if vib > 4.5:
        faults.append(f"HIGH VIBRATION {vib:.3f} mm/s (ISO 10816 limit 4.5 mm/s)")
    # Rule 12
    if vib > 7.1:
        faults.append(f"CRITICAL VIBRATION {vib:.3f} mm/s — bearing damage likely")
    # Rule 13 — RPM drop
    if len(rpms) >= 5 and (rpms[0] - rpms[-1]) > 80 and curr < 18:
        faults.append(f"UNEXPLAINED RPM DROP -{rpms[0]-rpms[-1]:.0f} RPM "
                       f"— mechanical drag or coupling issue")
    # Rule 14 — vibration trending
    if len(vibs) >= 5 and vibs[-1] - vibs[0] > 2:
        faults.append(f"VIBRATION RISING +{vibs[-1]-vibs[0]:.3f} mm/s "
                       f"in {len(vibs)}s — bearing degradation")

    # ── Advanced rules ────────────────────────────────────────────────────────
    # Rule 15 — slip anomaly (rotor bar fault)
    if rpm > 100 and curr > 2:
        actual_slip = (1500.0 - rpm) / 1500.0
        if actual_slip > 0.15:
            faults.append(f"HIGH SLIP {actual_slip*100:.1f}% "
                           f"— possible rotor bar fault or mechanical drag")
    # Rule 16 — stall detection
    if rpm < 30 and curr > 3.0:
        faults.append(f"POSSIBLE STALL: RPM={rpm:.0f} with I={curr:.1f}A "
                       f"— locked rotor risk, check load")
    # Rule 17 — phase imbalance proxy
    if volt > 370 and curr > I_RATED * 1.2 and RPM_RATED * 0.85 > rpm > 100:
        faults.append(f"POSSIBLE PHASE IMBALANCE: I={curr:.1f}A "
                       f"at V={volt:.0f}V RPM={rpm:.0f}")
    # Rule 18 — efficiency degradation
    # Estimate actual load from RPM slip: slip = (1500-rpm)/1500
    # Expected current scales with load fraction
    if curr > 2 and rpm > 100:
        actual_slip  = (1500.0 - rpm) / 1500.0
        load_est     = min(1.0, actual_slip / 0.05)   # slip=5% at 100% load
        load_est     = max(0.1, load_est)
        expected_curr = (P_RATED * load_est / EFFICIENCY) / (math.sqrt(3) * max(volt,1) * PF)
        # Only flag if current exceeds expected by more than 35% AND current is above rated
        if curr > expected_curr * 1.35 and curr > I_RATED * 0.85:
            faults.append(f"EFFICIENCY DEGRADATION: I={curr:.1f}A vs load-based expected "
                           f"{expected_curr:.1f}A (+{((curr/expected_curr-1)*100):.0f}%) — check load coupling")
    # Rule 19 — power factor proxy (high current, low power)
    power_kw = latest.get("power_kw", 0)
    if curr > 8 and power_kw < (curr * volt * math.sqrt(3) * 0.60) / 1000:
        faults.append(f"LOW POWER FACTOR: P={power_kw:.2f}kW vs I={curr:.1f}A "
                       f"— check capacitor bank")
    # Rule 20 — thermal resistance anomaly
    if curr > 5 and temp < T_AMBIENT + 5:
        faults.append(f"TEMPERATURE SENSOR ANOMALY: I={curr:.1f}A but T={temp:.1f}C "
                       f"— check sensor")
    # Rule 21 — current trend
    if len(currs) >= 10 and currs[-1] - currs[0] > 3:
        faults.append(f"CURRENT RISING +{currs[-1]-currs[0]:.1f}A "
                       f"in {len(currs)}s — increasing mechanical load")
    # Rule 22 — overvoltage + overtemp combined
    if volt > 420 and temp > 70:
        faults.append(f"OVERVOLTAGE + HIGH TEMP: V={volt:.0f}V T={temp:.1f}C "
                       f"— accelerated insulation aging")
    # Rule 23 — idle with current draw
    if rpm < 50 and curr > 2:
        faults.append(f"CURRENT DRAW AT IDLE: I={curr:.1f}A at RPM={rpm:.0f} "
                       f"— check contactor or drive")

    return faults


# ─── GEMINI DIAGNOSIS ─────────────────────────────────────────────────────────
def call_gemini(readings: list[dict], faults: list[str]) -> dict:
    """
    Send sensor data + faults to Gemini, get structured diagnosis.
    Returns dict with all 5 sections.
    """
    latest  = readings[-1]
    temps   = [r.get("temperature_c", 25) for r in readings]
    vibs    = [r.get("vibration_mm_s", 0)  for r in readings]
    rpms    = [r.get("rpm", 0)              for r in readings]
    currs   = [r.get("current_a", 0)        for r in readings]
    volts   = [r.get("voltage_v", 400)      for r in readings]

    def trend(v):
        return "rising" if v[-1] > v[0] * 1.05 else (
               "falling" if v[-1] < v[0] * 0.95 else "stable")

    data_str = "\n".join(
        f"{r.get('timestamp','')} RPM={r.get('rpm')} "
        f"T={r.get('temperature_c')}C Vib={r.get('vibration_mm_s')}mm/s "
        f"I={r.get('current_a')}A V={r.get('voltage_v')}V"
        for r in readings[-15:]
    )

    ftext = "\n".join(f"- {f}" for f in faults) if faults else "No threshold violations."

    system_text = (
        "You are FactoryGuard AI, a senior electrical engineer. "
        "Write in plain text only — no asterisks, no bold, no markdown. "
        "Motor: 3-phase induction motor, 400V nominal, 7.5kW, 1450 RPM rated, "
        "15.2A rated current, insulation class F, power factor 0.85. "
        "Normal ranges: voltage 380-420V, current below 15.2A, "
        "temperature below 80C, vibration below 4.5 mm/s ISO 10816."
    )

    user_text = f"""Sensor data (last {len(readings)} readings):
{data_str}

Trends: RPM {trend(rpms)}, temperature {trend(temps)}, vibration {trend(vibs)}, current {trend(currs)}, voltage {trend(volts)}.

Rule engine flagged:
{ftext}

Give a complete engineering diagnosis. IMPORTANT: write the content on the SAME LINE as each header, right after the colon. Never leave a header with no text.

STATUS: HEALTHY or WARNING or CRITICAL and one sentence why.
OBSERVATIONS: 2 sentences with specific values and percent deviations from rated.
ROOT CAUSE: 2-3 sentences explaining the physics with actual numbers.
RECOMMENDED ACTIONS:
Action 1 IMMEDIATE or THIS WEEK: specific action with tool or location.
Action 2 IMMEDIATE or THIS WEEK: specific action with tool or location.
Action 3 NEXT MAINTENANCE: preventive action.
RISK ASSESSMENT: one sentence with time to failure estimate, shutdown recommendation, safety risk level."""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            payload = json.dumps({
                "system_instruction": {"parts": [{"text": system_text}]},
                "contents": [{"role": "user", "parts": [{"text": user_text}]}],
                "generationConfig": {"temperature": 0.15, "maxOutputTokens": 1000},
            }).encode("utf-8")

            req = urllib.request.Request(
                GEMINI_URL, data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data     = json.loads(resp.read().decode())
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return _parse_diagnosis(raw_text)

        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 429:
                wait = 2 ** attempt * 5   # 5s, 10s, 20s
                print(f"[Gemini] Rate limit — retrying in {wait}s "
                      f"(attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            if e.code == 503:
                wait = 2 ** attempt * 3   # 3s, 6s, 12s
                print(f"[Gemini] Service unavailable — retrying in {wait}s")
                time.sleep(wait)
                continue
            return {"error": f"http_{e.code}", "message": body[:200]}
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return {"error": "connection", "message": str(e)}

    return {"error": "rate_limit",
            "message": "Gemini rate limit — all retries exhausted, retry in 60s"}


def _parse_diagnosis(text: str) -> dict:
    """Parse Gemini's plain-text response into structured sections."""
    result = {
        "status":       "",
        "observations": "",
        "root_cause":   "",
        "actions":      [],
        "risk":         "",
        "raw":          text,
    }
    current_section = None

    for line in text.split("\n"):
        s   = line.strip()
        if not s:
            continue
        low = s.lower()

        if low.startswith("status:"):
            result["status"] = s.split(":", 1)[1].strip()
            current_section  = "status"
        elif low.startswith("observations:"):
            result["observations"] = s.split(":", 1)[1].strip()
            current_section        = "observations"
        elif low.startswith("root cause:"):
            result["root_cause"] = s.split(":", 1)[1].strip()
            current_section      = "root_cause"
        elif low.startswith("recommended actions"):
            current_section = "actions"
        elif low.startswith("risk assessment:"):
            result["risk"]  = s.split(":", 1)[1].strip()
            current_section = "risk"
        elif low.startswith("action ") and ":" in s:
            result["actions"].append(s)
        elif current_section in ("observations", "root_cause", "risk") and s:
            # continuation lines
            key = {"observations": "observations",
                   "root_cause":   "root_cause",
                   "risk":         "risk"}[current_section]
            if result[key]:
                result[key] += " " + s
            else:
                result[key] = s

    return result


# ─── MAIN AGENT FUNCTION ──────────────────────────────────────────────────────
def run_diagnosis(
    load_pct: float          = 70.0,
    voltage_v: float         = 400.0,
    rpm_setpoint: float      = 1450.0,
    fault_bearing: bool      = False,
    fault_overtemp: bool     = False,
    fault_overcurrent: bool  = False,
    fault_voltage_drop: bool = False,
    history_seconds: int     = 30,
) -> dict:
    """
    Main entry point called by UiPath Agent Builder.
    Generates sensor history, runs fault engine, calls Gemini.
    Returns full JSON result for BPMN routing.
    """
    # Generate history (simulate N seconds of readings)
    readings = []
    for i in range(history_seconds):
        r = simulate_motor(
            load_pct=load_pct,
            voltage_v=voltage_v,
            rpm_setpoint=rpm_setpoint,
            fault_bearing=fault_bearing,
            fault_overtemp=fault_overtemp,
            fault_overcurrent=fault_overcurrent,
            fault_voltage_drop=fault_voltage_drop,
            noise=True,
        )
        readings.append(r)

    faults    = detect_faults(readings)
    latest    = readings[-1]
    diagnosis = call_gemini(readings, faults)

    # Determine severity for BPMN routing
    status = latest["status"]
    if "CRITICAL" in status:
        severity = "CRITICAL"
    elif "WARNING" in status or faults:
        severity = "WARNING"
    else:
        severity = "HEALTHY"

    result = {
        "agent":     "MotorMind AI v1.0",
        "timestamp": latest["timestamp"],
        "severity":  severity,
        "status":    status,
        "sensors":   {
            "rpm":            latest["rpm"],
            "temperature_c":  latest["temperature_c"],
            "vibration_mm_s": latest["vibration_mm_s"],
            "current_a":      latest["current_a"],
            "voltage_v":      latest["voltage_v"],
            "power_kw":       latest["power_kw"],
        },
        "faults_detected": len(faults),
        "fault_list":      faults,
        "diagnosis":       diagnosis,
        "bpmn_route":      _get_bpmn_route(severity),
    }

    return result


def _get_bpmn_route(severity: str) -> dict:
    """Tell UiPath Maestro BPMN which path to take."""
    routes = {
        "HEALTHY": {
            "path":         "log_healthy",
            "human_task":   False,
            "auto_alert":   False,
            "wait_seconds": 60,
            "message":      "Motor operating normally. Next check in 60 seconds.",
        },
        "WARNING": {
            "path":         "notify_engineer",
            "human_task":   True,
            "auto_alert":   False,
            "wait_seconds": 0,
            "message":      "WARNING detected. Engineer review required within 4 hours.",
        },
        "CRITICAL": {
            "path":         "emergency_escalation",
            "human_task":   True,
            "auto_alert":   True,
            "wait_seconds": 0,
            "message":      "CRITICAL fault. Immediate human approval required for shutdown.",
        },
    }
    return routes.get(severity, routes["HEALTHY"])


# ─── HTTP SERVER MODE (Flask — for UiPath Agent Builder + Render.com deploy) ──
def serve():
    """
    Full Flask HTTP server.
    Deploy this on Render.com for a permanent public URL.
    UiPath BPMN calls these endpoints instead of running Python locally.

    Endpoints:
      GET  /health              → health check (UiPath polls this)
      POST /api/diagnose        → full diagnosis (fault injection params from BPMN)
      GET  /api/latest          → latest sensor snapshot (BPMN Script task polls this)
      POST /api/diagnose/live   → diagnosis from raw sensor values (UiPath Agent inputs)
    """
    try:
        from flask import Flask as _Flask, request as _req, jsonify as _json
    except ImportError:
        print("Flask not installed. Run: pip install flask")
        return

    _app = _Flask("MotorMindAgent")

    # shared latest state — updated on every diagnose call
    _state = {
        "voltage_v": 400.0, "current_a": 0.0, "temperature_c": 25.0,
        "vibration_mm_s": 0.5, "rpm": 1450.0, "power_kw": 0.0,
        "status": "HEALTHY", "faults": "NONE", "severity": "HEALTHY",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    @_app.route("/health", methods=["GET"])
    def _health():
        return _json({"status": "ok", "agent": "MotorMind AI v1.0", "model": MODEL})

    @_app.route("/api/diagnose", methods=["POST"])
    def _diagnose():
        """
        Main endpoint — UiPath BPMN Script task POSTs here with fault params.
        Body (all optional, defaults to normal operation):
          load_pct, voltage_v, rpm_setpoint,
          fault_bearing, fault_overtemp, fault_overcurrent, fault_voltage_drop
        Returns full diagnosis JSON including severity for gateway routing.
        """
        d = _req.get_json(force=True, silent=True) or {}
        allowed = {"load_pct","voltage_v","rpm_setpoint","history_seconds",
                   "fault_bearing","fault_overtemp","fault_overcurrent","fault_voltage_drop"}
        kwargs = {k: v for k, v in d.items() if k in allowed}
        result = run_diagnosis(**kwargs)
        # update shared state for /api/latest
        s = result.get("sensors", {})
        _state.update({
            "voltage_v":      s.get("voltage_v", 400),
            "current_a":      s.get("current_a", 0),
            "temperature_c":  s.get("temperature_c", 25),
            "vibration_mm_s": s.get("vibration_mm_s", 0.5),
            "rpm":            s.get("rpm", 1450),
            "power_kw":       s.get("power_kw", 0),
            "status":         result.get("status", "HEALTHY"),
            "severity":       result.get("severity", "HEALTHY"),
            "faults":         ", ".join(result.get("fault_list", [])) or "NONE",
            "timestamp":      result.get("timestamp", ""),
        })
        return _json(result)

    @_app.route("/api/latest", methods=["GET"])
    def _latest():
        """
        UiPath BPMN Script task GETs this at process start to get live sensor values.
        Returns the 7 fields the MotorMind Agent task expects as inputs.
        """
        return _json(dict(_state))

    @_app.route("/api/diagnose/live", methods=["POST"])
    def _diagnose_live():
        """
        Called when UiPath Agent Builder passes live sensor values directly.
        Body: voltage_v, current_a, temperature_c, vibration_mm_s, rpm, status, faults
        Skips simulation — diagnoses from the provided values.
        """
        d = _req.get_json(force=True, silent=True) or {}
        voltage_v      = float(d.get("voltage_v",      400.0))
        current_a      = float(d.get("current_a",      0.0))
        temperature_c  = float(d.get("temperature_c",  25.0))
        vibration_mm_s = float(d.get("vibration_mm_s", 0.5))
        rpm            = float(d.get("rpm",             1450.0))
        status_in      = str(d.get("status",            "HEALTHY"))
        faults_in      = str(d.get("faults",            "NONE"))

        # Build synthetic reading so fault engine and Gemini can work
        reading = {
            "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rpm":            rpm,
            "temperature_c":  temperature_c,
            "vibration_mm_s": vibration_mm_s,
            "current_a":      current_a,
            "voltage_v":      voltage_v,
            "power_kw":       round((math.sqrt(3) * voltage_v * current_a * PF) / 1000, 3),
            "status":         status_in,
            "load_pct":       70.0,
        }
        readings = [reading] * 15  # pad to 15 so trend rules activate

        rule_faults = detect_faults(readings)
        if faults_in and faults_in != "NONE":
            for f in faults_in.split(","):
                f = f.strip()
                if f and f not in rule_faults:
                    rule_faults.append(f)

        diagnosis = call_gemini(readings, rule_faults)

        if "CRITICAL" in status_in or any("CRITICAL" in f for f in rule_faults):
            severity = "CRITICAL"
        elif "WARNING" in status_in or rule_faults:
            severity = "WARNING"
        else:
            severity = "HEALTHY"

        result = {
            "agent":           "MotorMind AI v1.0",
            "timestamp":       reading["timestamp"],
            "severity":        severity,
            "status":          status_in,
            "sensors":         {"rpm": rpm, "temperature_c": temperature_c,
                                "vibration_mm_s": vibration_mm_s, "current_a": current_a,
                                "voltage_v": voltage_v, "power_kw": reading["power_kw"]},
            "faults_detected": len(rule_faults),
            "fault_list":      rule_faults,
            "diagnosis":       diagnosis,
            "bpmn_route":      _get_bpmn_route(severity),
        }
        _state.update({"severity": severity, "status": status_in,
                       "faults": ", ".join(rule_faults) or "NONE"})
        return _json(result)

    port = int(os.environ.get("PORT", 8080))
    print(f"\n  MotorMind AI Agent — http://0.0.0.0:{port}")
    print(f"  GET  /health              → health check")
    print(f"  POST /api/diagnose        → full diagnosis (fault params)")
    print(f"  GET  /api/latest          → latest sensor snapshot")
    print(f"  POST /api/diagnose/live   → diagnosis from live sensor values\n")
    _app.run(host="0.0.0.0", port=port, debug=False)


# ─── CLI ENTRY POINT ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--serve" in sys.argv:
        serve()
    else:
        # Parse fault injection from CLI
        fault_map = {
            "bearing":    dict(fault_bearing=True),
            "overtemp":   dict(fault_overtemp=True),
            "overcurrent":dict(fault_overcurrent=True),
            "voltage":    dict(fault_voltage_drop=True),
            "combined":   dict(fault_bearing=True, fault_voltage_drop=True),
        }

        faults_kwargs = {}
        if "--simulate" in sys.argv:
            idx = sys.argv.index("--simulate")
            if idx + 1 < len(sys.argv):
                scenario = sys.argv[idx + 1]
                faults_kwargs = fault_map.get(scenario, {})
                print(f"Simulating fault scenario: {scenario}")

        print("Running MotorMind AI diagnosis...")
        result = run_diagnosis(**faults_kwargs)

        print("\n" + "="*60)
        print(f"SEVERITY : {result['severity']}")
        print(f"STATUS   : {result['status']}")
        print(f"FAULTS   : {result['faults_detected']} detected")
        print(f"BPMN     : route → {result['bpmn_route']['path']}")
        print("-"*60)
        if result["fault_list"]:
            print("FAULTS DETECTED:")
            for f in result["fault_list"]:
                print(f"  • {f}")
        print("-"*60)
        diag = result["diagnosis"]
        print(f"STATUS     : {diag.get('status','')}")
        print(f"OBSERVATIONS: {diag.get('observations','')}")
        print(f"ROOT CAUSE : {diag.get('root_cause','')}")
        print("ACTIONS:")
        for a in diag.get("actions", []):
            print(f"  {a}")
        print(f"RISK       : {diag.get('risk','')}")
        print("="*60)
        print("\nFull JSON output:")
        print(json.dumps(result, indent=2))
