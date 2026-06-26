"""
MotorMind AI — Web Interface v3
Fixed: non-blocking diagnosis, 1s live sensor updates, logo, all previous fixes
"""
from flask import Flask, render_template_string, request, jsonify
import json, os, sys, threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent"))
from motor_agent import run_diagnosis, simulate_motor

import csv, io
from datetime import datetime

app = Flask(__name__)
app.secret_key = "motormind-2026"

# ── Global state: latest sensor reading + diagnosis, updated every 1s by the browser
# UiPath polls /api/latest to get these values at BPMN process start
import threading as _threading
_state_lock = _threading.Lock()
_latest_state = {
    "voltage_v": 400.0, "current_a": 0.0, "temperature_c": 25.0,
    "vibration_mm_s": 0.5, "rpm": 1450.0, "power_kw": 0.0,
    "status": "HEALTHY", "faults": "NONE", "severity": "HEALTHY",
    "timestamp": "",
}

# In-memory fault log (WARNING and CRITICAL events only)
fault_log = []

def log_fault_event(result):
    """Log WARNING/CRITICAL events to in-memory log."""
    status = result.get("status","")
    if "WARNING" not in status and "CRITICAL" not in status:
        return
    s = result.get("sensors", {})
    fault_log.append({
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "severity":    result.get("severity",""),
        "status":      status,
        "voltage_v":   s.get("voltage_v",""),
        "current_a":   s.get("current_a",""),
        "temperature_c":s.get("temperature_c",""),
        "vibration_mm_s":s.get("vibration_mm_s",""),
        "rpm":         s.get("rpm",""),
        "power_kw":    s.get("power_kw",""),
        "faults":      " | ".join(result.get("fault_list",[])),
        "ai_status":   result.get("diagnosis",{}).get("status",""),
        "ai_risk":     result.get("diagnosis",{}).get("risk",""),
        "bpmn_route":  result.get("bpmn_route",{}).get("path",""),
    })

# Encode logo as base64 so it works without file serving
import base64, pathlib
LOGO_PATH = pathlib.Path(__file__).parent / "docs" / "logo.png"
LOGO_B64 = ""
if LOGO_PATH.exists():
    LOGO_B64 = "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode()

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MotorMind AI</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#f0f4ff; color:#1a1a2e; font-family:'Segoe UI',sans-serif; min-height:100vh; overflow:hidden; }

/* HEADER */
.header {
  background:linear-gradient(135deg,#ffffff,#f0f6ff,#e8f0ff);
  padding:12px 28px; display:flex; align-items:center; justify-content:space-between;
  box-shadow:0 2px 15px rgba(37,99,235,0.12); border-bottom:2px solid #bfdbfe;
  height:60px;
}
.header-brand { display:flex; align-items:center; gap:12px; }
.header-logo { width:70px; height:70px; object-fit:contain; }
.header-logo-placeholder { width:40px; height:40px; background:linear-gradient(135deg,#2563eb,#0ea5e9); border-radius:10px; display:flex; align-items:center; justify-content:center; color:#fff; font-size:1.2rem; }
.header-left h1 { color:#1e3a5f; font-size:1.3rem; font-weight:800; }
.header-left h1 span { color:#2563eb; }
.header-left p { color:#64748b; font-size:0.72rem; }
.live-badge {
  background:rgba(34,197,94,0.1); border:1px solid #22c55e; color:#16a34a;
  padding:5px 14px; border-radius:20px; font-size:0.75rem; font-weight:700;
  display:flex; align-items:center; gap:8px; animation:badge-glow 2s infinite;
}
@keyframes badge-glow { 0%,100%{box-shadow:0 0 0 0 rgba(34,197,94,0.3);} 50%{box-shadow:0 0 10px 3px rgba(34,197,94,0.1);} }
.live-dot { width:8px; height:8px; background:#22c55e; border-radius:50%; animation:dot-pulse 1.2s infinite; }
@keyframes dot-pulse { 0%,100%{transform:scale(1);} 50%{transform:scale(1.6);opacity:0.5;} }

/* LAYOUT — full viewport */
.main { display:grid; grid-template-columns:300px 1fr 360px; height:calc(100vh - 60px); overflow:hidden; }

/* LEFT SIDEBAR */
.sidebar { background:#fff; border-right:1px solid #e2e8f0; padding:16px; overflow-y:auto; }
.sidebar-title { font-size:0.68rem; font-weight:700; color:#94a3b8; letter-spacing:2px; text-transform:uppercase; margin-bottom:14px; }
.slider-group { margin-bottom:16px; }
.slider-label { display:flex; justify-content:space-between; margin-bottom:6px; }
.slider-label span:first-child { font-size:0.8rem; color:#475569; font-weight:600; }
.slider-value { background:#eff6ff; color:#2563eb; padding:2px 8px; border-radius:10px; font-size:0.78rem; font-weight:700; }
input[type=range] { width:100%; height:5px; background:#e2e8f0; border-radius:3px; outline:none; cursor:pointer; appearance:none; }
input[type=range]::-webkit-slider-thumb { appearance:none; width:16px; height:16px; background:linear-gradient(135deg,#2563eb,#0ea5e9); border-radius:50%; cursor:pointer; box-shadow:0 2px 6px rgba(37,99,235,0.4); transition:transform 0.2s; }
input[type=range]::-webkit-slider-thumb:hover { transform:scale(1.2); }
.divider { height:1px; background:#e2e8f0; margin:14px 0; }
.fault-title { font-size:0.68rem; font-weight:700; color:#94a3b8; letter-spacing:2px; text-transform:uppercase; margin-bottom:10px; }
.fault-grid { display:grid; grid-template-columns:1fr 1fr; gap:7px; margin-bottom:14px; }
.fault-btn { background:#f8fafc; border:2px solid #e2e8f0; color:#64748b; padding:8px 6px; border-radius:8px; font-size:0.73rem; font-weight:600; cursor:pointer; transition:all 0.2s; }
.fault-btn:hover { border-color:#2563eb; color:#2563eb; background:#eff6ff; }
.fault-btn.active { background:#fff0f0; border-color:#ef4444; color:#ef4444; box-shadow:0 0 10px rgba(239,68,68,0.2); }
.run-btn { width:100%; padding:12px; border:none; border-radius:10px; cursor:pointer; font-size:0.88rem; font-weight:700; background:linear-gradient(135deg,#2563eb,#0ea5e9); color:#fff; box-shadow:0 4px 12px rgba(37,99,235,0.35); transition:all 0.3s; }
.run-btn:hover { transform:translateY(-1px); box-shadow:0 6px 18px rgba(37,99,235,0.45); }
.run-btn:disabled { background:#94a3b8; box-shadow:none; transform:none; cursor:not-allowed; }
.auto-badge { text-align:center; margin-top:8px; color:#94a3b8; font-size:0.7rem; }
.countdown { color:#2563eb; font-weight:700; }
.trend-section { margin-top:14px; }
.trend-title { font-size:0.68rem; font-weight:700; color:#94a3b8; letter-spacing:2px; text-transform:uppercase; margin-bottom:4px; }
.trend-subtitle { font-size:0.65rem; color:#94a3b8; margin-bottom:10px; }
.trend-item { display:flex; align-items:center; margin-bottom:7px; }
.trend-name { font-size:0.72rem; color:#64748b; width:65px; flex-shrink:0; }
.trend-bar-bg { flex:1; height:5px; background:#e2e8f0; border-radius:3px; margin:0 7px; overflow:hidden; }
.trend-bar { height:100%; border-radius:3px; transition:width 0.8s ease, background 0.5s; }
.trend-arrow { font-size:0.78rem; width:18px; text-align:center; }
.trend-legend { display:flex; gap:10px; margin-top:8px; font-size:0.63rem; color:#64748b; }

/* CENTER */
.center { padding:14px; overflow-y:auto; }

/* STATUS */
.status-card { border-radius:14px; padding:14px 18px; margin-bottom:14px; display:flex; align-items:center; gap:12px; transition:all 0.5s; box-shadow:0 2px 12px rgba(0,0,0,0.07); }
.status-card.healthy { background:linear-gradient(135deg,#f0fdf4,#dcfce7); border:1px solid #86efac; }
.status-card.warning { background:linear-gradient(135deg,#fffbeb,#fef3c7); border:1px solid #fcd34d; }
.status-card.critical { background:linear-gradient(135deg,#fff1f2,#ffe4e6); border:1px solid #fca5a5; }
.status-dot { width:13px; height:13px; border-radius:50%; animation:pulse-ring 1.5s infinite; flex-shrink:0; }
.healthy .status-dot { background:#22c55e; }
.warning .status-dot { background:#f59e0b; }
.critical .status-dot { background:#ef4444; }
@keyframes pulse-ring { 0%{transform:scale(1);} 70%{transform:scale(1.2);} 100%{transform:scale(1);} }
.status-info h3 { font-size:1rem; font-weight:700; }
.healthy .status-info h3 { color:#15803d; }
.warning .status-info h3 { color:#b45309; }
.critical .status-info h3 { color:#b91c1c; }
.status-info p { font-size:0.75rem; color:#64748b; margin-top:1px; }
.status-right { margin-left:auto; font-size:0.72rem; color:#94a3b8; text-align:right; }

/* METRICS */
.metrics { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:12px; }
.metric-card { background:#fff; border-radius:12px; padding:14px; box-shadow:0 2px 8px rgba(0,0,0,0.05); border:1px solid #e2e8f0; transition:all 0.3s; position:relative; overflow:hidden; }
.metric-card:hover { transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,0,0,0.1); }
.metric-card::before { content:''; position:absolute; top:0; left:0; right:0; height:3px; background:linear-gradient(90deg,#2563eb,#0ea5e9); transform:scaleX(0); transform-origin:left; transition:transform 0.4s; }
.metric-card:hover::before { transform:scaleX(1); }
.metric-card.warn::before { background:linear-gradient(90deg,#f59e0b,#fbbf24); transform:scaleX(1); }
.metric-card.crit::before { background:linear-gradient(90deg,#ef4444,#f87171); transform:scaleX(1); }
.metric-label { font-size:0.65rem; color:#94a3b8; letter-spacing:1px; text-transform:uppercase; margin-bottom:4px; }
.metric-value { font-size:1.7rem; font-weight:800; color:#1e3a5f; font-family:monospace; transition:color 0.5s, transform 0.2s; }
.metric-value.warn { color:#d97706; }
.metric-value.crit { color:#dc2626; }
.metric-value.ok { color:#16a34a; }
.metric-unit { font-size:0.68rem; color:#94a3b8; }
.metric-trend { font-size:0.68rem; margin-top:4px; font-weight:600; }
.metric-trend.up { color:#ef4444; }
.metric-trend.down { color:#2563eb; }
.metric-trend.stable { color:#94a3b8; }

/* FAULT TAGS */
.fault-tags { display:flex; flex-wrap:wrap; gap:5px; margin-bottom:12px; }
.fault-tag { background:#fff0f0; border:1px solid #fca5a5; color:#dc2626; padding:3px 10px; border-radius:20px; font-size:0.7rem; font-weight:600; animation:tag-appear 0.3s ease; }
@keyframes tag-appear { from{opacity:0;transform:scale(0.8);} to{opacity:1;transform:scale(1);} }
.no-fault { background:#f0fdf4; border:1px solid #86efac; color:#15803d; padding:5px 14px; border-radius:20px; font-size:0.75rem; font-weight:600; display:inline-block; margin-bottom:12px; }

/* HISTORY ALERT */
.history-alert { background:#fff7ed; border:1px solid #fed7aa; border-radius:10px; padding:8px 14px; margin-bottom:10px; font-size:0.78rem; color:#9a3412; display:none; }
.history-alert.show { display:block; animation:slide-in 0.3s ease; }
@keyframes slide-in { from{opacity:0;transform:translateY(-8px);} to{opacity:1;transform:translateY(0);} }

/* DIAGNOSIS */
.diag-card { background:#fff; border-radius:14px; padding:18px; box-shadow:0 2px 8px rgba(0,0,0,0.05); border:1px solid #e2e8f0; }
.diag-header { font-size:0.68rem; color:#94a3b8; letter-spacing:2px; text-transform:uppercase; margin-bottom:14px; display:flex; align-items:center; gap:6px; }
.diag-section { margin-bottom:12px; padding-bottom:12px; border-bottom:1px solid #f1f5f9; }
.diag-section:last-child { border-bottom:none; margin-bottom:0; padding-bottom:0; }
.diag-section-label { font-size:0.68rem; font-weight:700; letter-spacing:1px; text-transform:uppercase; margin-bottom:5px; }
.status-label { color:#2563eb; } .obs-label { color:#7c3aed; } .root-label { color:#0891b2; }
.action-label { color:#d97706; } .risk-label { color:#dc2626; }
.diag-text { font-size:0.83rem; color:#475569; line-height:1.7; }
.action-item { font-size:0.8rem; padding:5px 10px; border-radius:7px; margin:3px 0; }
.action-item.immediate { background:#fff0f0; color:#dc2626; border-left:3px solid #ef4444; }
.action-item.week { background:#fffbeb; color:#b45309; border-left:3px solid #f59e0b; }
.action-item.maintenance { background:#f0f9ff; color:#0369a1; border-left:3px solid #0ea5e9; }
.bpmn-box { background:linear-gradient(135deg,#eff6ff,#f0f9ff); border:1px solid #bfdbfe; border-radius:10px; padding:10px 14px; margin-top:12px; }
.bpmn-label { font-size:0.62rem; font-weight:700; color:#94a3b8; letter-spacing:2px; text-transform:uppercase; margin-bottom:3px; }
.bpmn-path { font-size:0.88rem; font-weight:800; color:#2563eb; }
.bpmn-msg { font-size:0.75rem; color:#64748b; margin-top:2px; }
.placeholder { color:#cbd5e1; text-align:center; padding:30px; font-size:0.83rem; }

/* CHAT */
.chat-panel { background:#fff; border-left:1px solid #e2e8f0; display:flex; flex-direction:column; height:100%; overflow:hidden; }
.chat-header { padding:14px 18px; border-bottom:1px solid #e2e8f0; background:linear-gradient(135deg,#f8faff,#fff); flex-shrink:0; display:flex; align-items:center; gap:10px; }
.chat-header-icon { width:32px; height:32px; background:linear-gradient(135deg,#2563eb,#0ea5e9); border-radius:8px; display:flex; align-items:center; justify-content:center; color:#fff; font-size:0.9rem; }
.chat-header h3 { color:#1e3a5f; font-size:0.88rem; font-weight:700; }
.chat-header p { color:#94a3b8; font-size:0.7rem; }
.chat-messages { flex:1; overflow-y:auto; overflow-x:hidden; padding:14px; display:flex; flex-direction:column; gap:10px; min-height:0; }
.msg { padding:10px 13px; border-radius:12px; font-size:0.8rem; line-height:1.6; max-width:96%; animation:msg-appear 0.3s ease; }
@keyframes msg-appear { from{opacity:0;transform:translateY(6px);} to{opacity:1;transform:translateY(0);} }
.msg.user { background:linear-gradient(135deg,#2563eb,#0ea5e9); color:#fff; align-self:flex-end; border-bottom-right-radius:3px; }
.msg.agent { background:#f8fafc; border:1px solid #e2e8f0; color:#334155; align-self:flex-start; border-bottom-left-radius:3px; }
.msg .role { font-size:0.63rem; font-weight:700; margin-bottom:4px; opacity:0.75; }
.msg-section { font-weight:700; color:#1e3a5f; margin-top:7px; margin-bottom:2px; font-size:0.73rem; text-transform:uppercase; letter-spacing:0.5px; border-bottom:1px solid #e2e8f0; padding-bottom:2px; }
.msg-line { margin-bottom:3px; color:#475569; }
.msg-bullet { padding-left:12px; color:#475569; position:relative; margin-bottom:2px; }
.msg-bullet::before { content:'•'; position:absolute; left:0; color:#2563eb; }
.suggestions { padding:8px 14px; display:flex; flex-wrap:wrap; gap:5px; border-top:1px solid #e2e8f0; flex-shrink:0; }
.suggestion { background:#eff6ff; border:1px solid #bfdbfe; color:#2563eb; padding:4px 10px; border-radius:20px; font-size:0.7rem; cursor:pointer; font-weight:600; transition:all 0.2s; }
.suggestion:hover { background:#2563eb; color:#fff; }
.spinner { display:none; padding:6px 14px; color:#94a3b8; font-size:0.75rem; flex-shrink:0; }
.typing { display:inline-flex; gap:4px; align-items:center; }
.typing span { width:5px; height:5px; background:#94a3b8; border-radius:50%; animation:typing 1.2s infinite; }
.typing span:nth-child(2){animation-delay:0.2s;} .typing span:nth-child(3){animation-delay:0.4s;}
@keyframes typing { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-4px);} }
.chat-input-row { padding:10px 14px; border-top:1px solid #e2e8f0; display:flex; gap:7px; flex-shrink:0; }
.chat-input { flex:1; background:#f8fafc; border:2px solid #e2e8f0; color:#334155; padding:9px 12px; border-radius:9px; font-size:0.8rem; outline:none; transition:border-color 0.2s; }
.chat-input:focus { border-color:#2563eb; background:#fff; }
.send-btn { background:linear-gradient(135deg,#2563eb,#0ea5e9); color:#fff; border:none; padding:9px 16px; border-radius:9px; cursor:pointer; font-size:0.8rem; font-weight:700; transition:all 0.2s; }
.send-btn:hover { transform:scale(1.05); }

/* LOADING STATE */
.diag-loading { display:flex; align-items:center; gap:10px; padding:20px; color:#94a3b8; font-size:0.82rem; }
.diag-spinner { width:20px; height:20px; border:2px solid #e2e8f0; border-top-color:#2563eb; border-radius:50%; animation:spin 0.8s linear infinite; }
@keyframes spin { to{transform:rotate(360deg);} }
</style>
</head>
<body>

<div class="header">
  <div class="header-brand">
    LOGO_PLACEHOLDER
    <div class="header-left">
      <h1>Motor<span>Mind</span> AI</h1>
      <p>3-Phase 400V · Real-Time Predictive Maintenance · UiPath Maestro BPMN</p>
    </div>
  </div>
  <div class="live-badge"><div class="live-dot"></div> LIVE MONITORING</div>
</div>

<div class="main">
  <!-- SIDEBAR -->
  <div class="sidebar">
    <div class="sidebar-title">⚙ Motor Simulator</div>
    <div class="slider-group">
      <div class="slider-label"><span>Load</span><span class="slider-value" id="v-load">70%</span></div>
      <input type="range" id="load" min="0" max="100" value="70" oninput="document.getElementById('v-load').textContent=this.value+'%'">
    </div>
    <div class="slider-group">
      <div class="slider-label"><span>Supply Voltage</span><span class="slider-value" id="v-volt">400 V</span></div>
      <input type="range" id="voltage" min="280" max="440" value="400" oninput="document.getElementById('v-volt').textContent=this.value+' V'">
    </div>
    <div class="slider-group">
      <div class="slider-label"><span>RPM Setpoint</span><span class="slider-value" id="v-rpm">1450</span></div>
      <input type="range" id="rpm" min="0" max="1500" value="1450" oninput="document.getElementById('v-rpm').textContent=this.value">
    </div>
    <div class="divider"></div>
    <div class="fault-title">⚡ Fault Injection</div>
    <div class="fault-grid">
      <button class="fault-btn" id="btn-bearing" onclick="toggleFault('bearing')">🔩 Bearing</button>
      <button class="fault-btn" id="btn-overtemp" onclick="toggleFault('overtemp')">🌡 Overtemp</button>
      <button class="fault-btn" id="btn-voltage" onclick="toggleFault('voltage')">⚡ Volt Drop</button>
      <button class="fault-btn" id="btn-overcurrent" onclick="toggleFault('overcurrent')">⚠ Overcurrent</button>
    </div>
    <button class="run-btn" id="run-btn" onclick="runDiagnosis()">▶ RUN DIAGNOSIS</button>
    <div class="auto-badge">Auto AI refresh in <span class="countdown" id="countdown">30</span>s · sensors every 1s</div>
    <div class="divider"></div>
    <div class="trend-section">
      <div class="trend-title">📈 Live Trends</div>
      <div class="trend-subtitle">Bar = % of safe limit · 🟢 Safe 🟡 Warn 🔴 Critical · ↑↓ direction</div>
      <div class="trend-item"><div class="trend-name">Voltage</div><div class="trend-bar-bg"><div class="trend-bar" id="tr-volt" style="width:80%;background:#22c55e"></div></div><div class="trend-arrow" id="ta-volt">—</div></div>
      <div class="trend-item"><div class="trend-name">Current</div><div class="trend-bar-bg"><div class="trend-bar" id="tr-curr" style="width:60%;background:#22c55e"></div></div><div class="trend-arrow" id="ta-curr">—</div></div>
      <div class="trend-item"><div class="trend-name">Temp °C</div><div class="trend-bar-bg"><div class="trend-bar" id="tr-temp" style="width:40%;background:#22c55e"></div></div><div class="trend-arrow" id="ta-temp">—</div></div>
      <div class="trend-item"><div class="trend-name">Vibration</div><div class="trend-bar-bg"><div class="trend-bar" id="tr-vib" style="width:20%;background:#22c55e"></div></div><div class="trend-arrow" id="ta-vib">—</div></div>
      <div class="trend-item"><div class="trend-name">RPM</div><div class="trend-bar-bg"><div class="trend-bar" id="tr-rpm" style="width:90%;background:#22c55e"></div></div><div class="trend-arrow" id="ta-rpm">—</div></div>
    </div>
    <!-- Mini status in sidebar -->
    <div class="divider"></div>
    <div id="sidebar-status" style="font-size:0.72rem;color:#64748b;text-align:center;">Initializing...</div>
  </div>

  <!-- CENTER -->
  <div class="center">
    <div class="history-alert" id="history-alert">⚠ <strong>Trend anomaly:</strong> <span id="alert-msg"></span></div>
    <div class="status-card healthy" id="status-card">
      <div class="status-dot"></div>
      <div class="status-info"><h3 id="status-title">Initializing...</h3><p id="status-sub">Loading first diagnosis</p></div>
      <div class="status-right" id="status-time"></div>
    </div>
    <div class="metrics">
      <div class="metric-card" id="mc-rpm"><div class="metric-label">RPM</div><div class="metric-value" id="m-rpm">—</div><div class="metric-trend stable" id="mt-rpm">—</div></div>
      <div class="metric-card" id="mc-temp"><div class="metric-label">Temperature</div><div class="metric-value" id="m-temp">—</div><div class="metric-unit">°C · limit 80</div><div class="metric-trend stable" id="mt-temp">—</div></div>
      <div class="metric-card" id="mc-vib"><div class="metric-label">Vibration</div><div class="metric-value" id="m-vib">—</div><div class="metric-unit">mm/s · limit 4.5</div><div class="metric-trend stable" id="mt-vib">—</div></div>
      <div class="metric-card" id="mc-curr"><div class="metric-label">Current</div><div class="metric-value" id="m-curr">—</div><div class="metric-unit">A · rated 15.2</div><div class="metric-trend stable" id="mt-curr">—</div></div>
      <div class="metric-card" id="mc-volt"><div class="metric-label">Voltage</div><div class="metric-value" id="m-volt">—</div><div class="metric-unit">V · rated 400</div><div class="metric-trend stable" id="mt-volt">—</div></div>
      <div class="metric-card" id="mc-pow"><div class="metric-label">Power</div><div class="metric-value" id="m-pow">—</div><div class="metric-unit">kW · rated 7.5</div><div class="metric-trend stable" id="mt-pow">—</div></div>
    </div>
    <div id="fault-container"></div>
    <div class="diag-card">
      <div class="diag-header">🤖 AI DIAGNOSIS</div>
      <div id="diagnosis-content"><div class="placeholder">Run a diagnosis to see AI analysis</div></div>
    </div>
    <!-- FAULT LOG -->
    <div class="diag-card" style="margin-top:12px;">
      <div class="diag-header" style="display:flex;justify-content:space-between;align-items:center;">
        <span>📋 FAULT LOG <span id="log-count" style="color:#94a3b8;font-weight:400">(0 events)</span></span>
        <div style="display:flex;gap:8px;">
          <button onclick="downloadCSV()" style="background:#2563eb;color:#fff;border:none;padding:4px 12px;border-radius:6px;font-size:0.72rem;cursor:pointer;font-weight:700;">⬇ CSV</button>
          <button onclick="clearLog()" style="background:#f1f5f9;color:#64748b;border:1px solid #e2e8f0;padding:4px 12px;border-radius:6px;font-size:0.72rem;cursor:pointer;">Clear</button>
        </div>
      </div>
      <div id="fault-log-table" style="max-height:160px;overflow-y:auto;font-size:0.75rem;">
        <div class="placeholder" style="padding:16px">No WARNING or CRITICAL events yet — motor is healthy</div>
      </div>
    </div>
  </div>

  <!-- CHAT -->
  <div class="chat-panel">
    <div class="chat-header">
      <div class="chat-header-icon">🤖</div>
      <div><h3>MotorMind Agent</h3><p>Ask anything · history-aware · Gemini AI</p></div>
    </div>
    <div class="chat-messages" id="chat-messages">
      <div class="msg agent"><div class="role">MotorMind Agent</div>Hello! I monitor your motor in real time. I analyze live sensor data and the last 20 readings to detect trends. Run a diagnosis or ask me anything.</div>
    </div>
    <div class="suggestions" id="suggestions">
      <div class="suggestion" onclick="sendSuggestion(this)">What is wrong?</div>
      <div class="suggestion" onclick="sendSuggestion(this)">Safe to keep running?</div>
      <div class="suggestion" onclick="sendSuggestion(this)">Explain root cause</div>
      <div class="suggestion" onclick="sendSuggestion(this)">What to do first?</div>
    </div>
    <div class="spinner" id="spinner"><div class="typing"><span></span><span></span><span></span></div> Agent thinking...</div>
    <div class="chat-input-row">
      <input class="chat-input" id="chat-input" type="text" placeholder="Ask the agent..." onkeydown="if(event.key==='Enter')sendMessage()">
      <button class="send-btn" onclick="sendMessage()">Send</button>
    </div>
  </div>
</div>

<script>
const faults = {bearing:false,overtemp:false,voltage:false,overcurrent:false};
let lastResult = null;
let history = [];
let countdown = 30;
let countdownTimer = null;
let diagnosisRunning = false;

function toggleFault(n) {
  faults[n] = !faults[n];
  document.getElementById('btn-'+n).classList.toggle('active', faults[n]);
}

function sevClass(status) {
  if (!status) return 'healthy';
  const s = status.toUpperCase();
  return s.includes('CRITICAL') ? 'critical' : s.includes('WARNING') ? 'warning' : 'healthy';
}

function animateValue(id, val) {
  const el = document.getElementById(id);
  if (!el || val === undefined || val === null) return;
  const newVal = String(val);
  if (el.textContent === newVal) return;
  el.style.transform = 'scale(1.08)';
  el.textContent = newVal;
  setTimeout(() => { el.style.transform = 'scale(1)'; el.style.transition = 'transform 0.25s'; }, 80);
}

function trendArrow(arr) {
  if (arr.length < 4) return {arrow:'—', cls:'stable'};
  const first = arr.slice(0,3).reduce((a,b)=>a+b,0)/3;
  const last  = arr.slice(-3).reduce((a,b)=>a+b,0)/3;
  const diff  = ((last-first)/(Math.abs(first)||1))*100;
  if (diff > 2) return {arrow:'↑', cls:'up'};
  if (diff < -2) return {arrow:'↓', cls:'down'};
  return {arrow:'→', cls:'stable'};
}

function updateTrendBars() {
  if (history.length < 2) return;

  // Voltage — green when normal (380-420), orange when too low (<360) OR too high (>420), red critical
  const volts = history.map(r=>parseFloat(r.voltage_v||400));
  const lv = volts[volts.length-1];
  const voltPct = Math.min(100,(lv/440)*100);
  const voltColor = (lv<340||lv>430)?'#ef4444':(lv<360||lv>420)?'#f59e0b':'#22c55e';
  const vb = document.getElementById('tr-volt');
  if (vb) { vb.style.width=voltPct+'%'; vb.style.background=voltColor; }
  const vt = trendArrow(volts);
  const vta = document.getElementById('ta-volt');
  if (vta) { vta.textContent=vt.arrow; vta.style.color='#94a3b8'; }

  const defs = [
    {key:'current_a',   max:25,  warn:68, el:'tr-curr',ta:'ta-curr', invertArrow:false},
    {key:'temperature_c',max:110,warn:73, el:'tr-temp',ta:'ta-temp', invertArrow:false},
    {key:'vibration_mm_s',max:12,warn:38, el:'tr-vib', ta:'ta-vib',  invertArrow:false},
    {key:'rpm',          max:1500,warn:15,el:'tr-rpm', ta:'ta-rpm',  invertArrow:true},
  ];
  defs.forEach(f => {
    const vals = history.map(r=>parseFloat(r[f.key]||0));
    const latest = vals[vals.length-1];
    let pct, color;
    if (f.invertArrow) {
      pct = Math.min(100,(latest/f.max)*100);
      color = latest<100?'#ef4444':latest<500?'#f59e0b':'#22c55e';
    } else {
      pct = Math.min(100,(latest/f.max)*100);
      color = pct>f.warn*1.2?'#ef4444':pct>f.warn?'#f59e0b':'#22c55e';
    }
    const bar = document.getElementById(f.el);
    if (bar) { bar.style.width=pct+'%'; bar.style.background=color; }
    const t = trendArrow(vals);
    const ta = document.getElementById(f.ta);
    let taColor;
    if (f.invertArrow) taColor = t.cls==='down'?'#ef4444':t.cls==='up'?'#22c55e':'#94a3b8';
    else taColor = t.cls==='up'?'#ef4444':t.cls==='down'?'#2563eb':'#94a3b8';
    if (ta) { ta.textContent=t.arrow; ta.style.color=taColor; }
  });
}

function checkHistoryAnomalies() {
  if (history.length < 5) return;
  const alerts = [];
  const rpms  = history.slice(-5).map(r=>parseFloat(r.rpm||0));
  const currs = history.slice(-5).map(r=>parseFloat(r.current_a||0));
  const temps = history.slice(-10).map(r=>parseFloat(r.temperature_c||0));
  const rpmDrop = rpms[0]-rpms[rpms.length-1];
  if (rpmDrop>150) alerts.push(`RPM dropped ${rpmDrop.toFixed(0)} in last 5s — possible overload or forced stop`);
  const currRise = currs[currs.length-1]-currs[0];
  if (currRise>3) alerts.push(`Current rising +${currRise.toFixed(1)}A — increasing load`);
  if (temps.length>=10) { const tr=temps[temps.length-1]-temps[0]; if(tr>8) alerts.push(`Temperature rising +${tr.toFixed(1)}°C — thermal accumulation risk`); }
  const alertEl = document.getElementById('history-alert');
  if (alerts.length>0) { document.getElementById('alert-msg').textContent=alerts[0]; alertEl.classList.add('show'); }
  else alertEl.classList.remove('show');
}

function updateMetrics(sensors, status) {
  const sc = sevClass(status);
  animateValue('m-rpm',  sensors.rpm??'—');
  animateValue('m-temp', sensors.temperature_c??'—');
  animateValue('m-vib',  sensors.vibration_mm_s??'—');
  animateValue('m-curr', sensors.current_a??'—');
  animateValue('m-volt', sensors.voltage_v??'—');
  animateValue('m-pow',  sensors.power_kw??'—');

  const t=parseFloat(sensors.temperature_c||0), v=parseFloat(sensors.vibration_mm_s||0),
        c=parseFloat(sensors.current_a||0),     vol=parseFloat(sensors.voltage_v||0);

  document.getElementById('mc-temp').className='metric-card '+(t>=100?'crit':t>=80?'warn':'');
  document.getElementById('m-temp').className='metric-value '+(t>=100?'crit':t>=80?'warn':sc==='healthy'?'ok':'');
  document.getElementById('mc-vib').className='metric-card '+(v>=7.1?'crit':v>=4.5?'warn':'');
  document.getElementById('m-vib').className='metric-value '+(v>=7.1?'crit':v>=4.5?'warn':sc==='healthy'?'ok':'');
  document.getElementById('mc-curr').className='metric-card '+(c>=22?'crit':c>=17?'warn':'');
  document.getElementById('m-curr').className='metric-value '+(c>=22?'crit':c>=17?'warn':sc==='healthy'?'ok':'');
  document.getElementById('mc-volt').className='metric-card '+(vol<=340?'crit':vol<=360?'warn':'');
  document.getElementById('m-volt').className='metric-value '+(vol<=340?'crit':vol<=360?'warn':sc==='healthy'?'ok':'');

  if (history.length>=2) {
    [['mt-rpm','rpm'],['mt-temp','temperature_c'],['mt-vib','vibration_mm_s'],
     ['mt-curr','current_a'],['mt-volt','voltage_v'],['mt-pow','power_kw']].forEach(([id,key])=>{
      const vals=history.map(r=>parseFloat(r[key]||0));
      const t=trendArrow(vals);
      const el=document.getElementById(id);
      if (el) { el.textContent=t.arrow+(t.cls!=='stable'?' '+Math.abs(((vals[vals.length-1]-vals[0])/(vals[0]||1))*100).toFixed(1)+'%':''); el.className='metric-trend '+t.cls; }
    });
  }
}

function renderDiagnosis(result) {
  lastResult = result;
  if (result.sensors) { history.push(result.sensors); if(history.length>20)history.shift(); }

  const status = result.status||'HEALTHY';
  const sc = sevClass(status);

  // Status card
  const card = document.getElementById('status-card');
  card.className = 'status-card '+sc;
  const titles = {healthy:'✓ Motor Healthy', warning:'⚠ Warning Detected', critical:'🔴 Critical Fault'};
  document.getElementById('status-title').textContent = titles[sc]||'—';
  document.getElementById('status-sub').textContent = status.replace(/_/g,' ');
  document.getElementById('status-time').textContent = new Date().toLocaleTimeString();
  document.getElementById('sidebar-status').textContent = titles[sc]||'—';

  updateMetrics(result.sensors||{}, status);

  // Faults
  const flist = result.fault_list||[];
  const fc = document.getElementById('fault-container');
  fc.innerHTML = flist.length>0
    ? '<div class="fault-tags">'+flist.map(f=>'<span class="fault-tag">'+f+'</span>').join('')+'</div>'
    : '<span class="no-fault">✓ All parameters within normal range</span>';

  updateTrendBars();
  checkHistoryAnomalies();

  // Diagnosis
  const d = result.diagnosis;
  let html = '';
  if (d && !d.error) {
    const sc2 = sc==='critical'?'risk-label':sc==='warning'?'action-label':'status-label';
    html += `<div class="diag-section"><div class="diag-section-label ${sc2}">STATUS</div><div class="diag-text">${d.status||'—'}</div></div>`;
    html += `<div class="diag-section"><div class="diag-section-label obs-label">OBSERVATIONS</div><div class="diag-text">${d.observations||'—'}</div></div>`;
    html += `<div class="diag-section"><div class="diag-section-label root-label">ROOT CAUSE</div><div class="diag-text">${d.root_cause||'—'}</div></div>`;
    if ((d.actions||[]).length>0) {
      html += '<div class="diag-section"><div class="diag-section-label action-label">RECOMMENDED ACTIONS</div>';
      d.actions.forEach(a=>{ const cls=a.includes('IMMEDIATE')?'immediate':a.includes('THIS WEEK')?'week':'maintenance'; html+=`<div class="action-item ${cls}">${a}</div>`; });
      html += '</div>';
    }
    html += `<div class="diag-section"><div class="diag-section-label risk-label">RISK ASSESSMENT</div><div class="diag-text">${d.risk||'—'}</div></div>`;
  } else if (d?.error) {
    html = `<div style="color:#dc2626;font-size:0.8rem;padding:8px">⚠ ${d.message}<br><small>Sensor data is still live. AI will retry on next cycle.</small></div>`;
  }
  const route = result.bpmn_route||{};
  html += `<div class="bpmn-box"><div class="bpmn-label">UiPath Maestro BPMN Route</div><div class="bpmn-path">→ ${route.path||'—'}</div><div class="bpmn-msg">${route.message||''}</div></div>`;
  document.getElementById('diagnosis-content').innerHTML = html;
}

async function runDiagnosis(silent=false) {
  if (diagnosisRunning) return;
  diagnosisRunning = true;
  const btn = document.getElementById('run-btn');
  if (!silent) { btn.disabled=true; btn.textContent='⟳ AI Analyzing...'; }
  document.getElementById('diagnosis-content').innerHTML = '<div class="diag-loading"><div class="diag-spinner"></div>Gemini AI is analyzing motor data...</div>';

  const payload = {
    load_pct: parseFloat(document.getElementById('load').value),
    voltage_v: parseFloat(document.getElementById('voltage').value),
    rpm_setpoint: parseFloat(document.getElementById('rpm').value),
    fault_bearing: faults.bearing, fault_overtemp: faults.overtemp,
    fault_overcurrent: faults.overcurrent, fault_voltage_drop: faults.voltage,
  };

  try {
    const resp = await fetch('/api/diagnose', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
    const result = await resp.json();
    renderDiagnosis(result);
    refreshLog();
  } catch(e) {
    document.getElementById('diagnosis-content').innerHTML = `<div style="color:#dc2626;padding:10px">Error: ${e.message}</div>`;
  }
  diagnosisRunning = false;
  if (!silent) { btn.disabled=false; btn.textContent='▶ RUN DIAGNOSIS'; }
  resetCountdown();
}

// FAST SENSOR UPDATE — every 1 second, no Gemini call
async function fetchLiveSensors() {
  const payload = {
    load_pct: parseFloat(document.getElementById('load').value),
    voltage_v: parseFloat(document.getElementById('voltage').value),
    rpm_setpoint: parseFloat(document.getElementById('rpm').value),
    fault_bearing: faults.bearing, fault_overtemp: faults.overtemp,
    fault_overcurrent: faults.overcurrent, fault_voltage_drop: faults.voltage,
  };
  try {
    const resp = await fetch('/api/sensors', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
    const s = await resp.json();
    animateValue('m-rpm',  s.rpm);
    animateValue('m-temp', s.temperature_c);
    animateValue('m-vib',  s.vibration_mm_s);
    animateValue('m-curr', s.current_a);
    animateValue('m-volt', s.voltage_v);
    animateValue('m-pow',  s.power_kw);
    history.push(s); if(history.length>20)history.shift();
    updateTrendBars();
    checkHistoryAnomalies();
    updateMetrics(s, s.status||'HEALTHY');
  } catch(e) {}
}

function resetCountdown() {
  countdown = 30;
  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = setInterval(()=>{
    countdown--;
    document.getElementById('countdown').textContent = countdown;
    if (countdown<=0) { runDiagnosis(true); countdown=30; }
  }, 1000);
}

function formatAgentMsg(text) {
  const lines = text.split('\n').filter(l=>l.trim());
  let html = '';
  lines.forEach(line => {
    const s = line.trim();
    if (s.match(/^[A-Z][A-Z\s]{2,}:/)) {
      const [label, ...rest] = s.split(':');
      html += `<div class="msg-section">${label}</div>`;
      if (rest.join(':').trim()) html += `<div class="msg-line">${rest.join(':').trim()}</div>`;
    } else if (s.startsWith('Action ')||s.startsWith('•')||s.startsWith('-')) {
      html += `<div class="msg-bullet">${s.replace(/^[-•]\s*/,'')}</div>`;
    } else {
      html += `<div class="msg-line">${s}</div>`;
    }
  });
  return html || `<div class="msg-line">${text}</div>`;
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  document.getElementById('suggestions').style.display = 'none';
  appendMsg('user','You',text);
  document.getElementById('spinner').style.display = 'flex';
  try {
    const resp = await fetch('/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:text,last_result:lastResult,history:history.slice(-10)}) });
    const data = await resp.json();
    appendMsg('agent','MotorMind Agent',data.response);
  } catch(e) { appendMsg('agent','MotorMind Agent','Error: '+e.message); }
  document.getElementById('spinner').style.display = 'none';
}

function sendSuggestion(el) { document.getElementById('chat-input').value=el.textContent; sendMessage(); }

function appendMsg(role, label, text) {
  const c = document.getElementById('chat-messages');
  const d = document.createElement('div');
  d.className = 'msg '+role;
  const content = role==='agent' ? formatAgentMsg(text) : `<div class="msg-line">${text}</div>`;
  d.innerHTML = `<div class="role">${label}</div>${content}`;
  c.appendChild(d);
  c.scrollTop = c.scrollHeight;
}

// FAULT LOG
async function refreshLog() {
  try {
    const resp = await fetch('/api/log');
    const data = await resp.json();
    document.getElementById('log-count').textContent = `(${data.count} events)`;
    const table = document.getElementById('fault-log-table');
    if (!data.events.length) {
      table.innerHTML = '<div class="placeholder" style="padding:16px">No WARNING or CRITICAL events yet</div>';
      return;
    }
    let html = '<table style="width:100%;border-collapse:collapse;">';
    html += '<tr style="background:#f8fafc;font-size:0.68rem;color:#94a3b8;"><th style="padding:4px 6px;text-align:left">Time</th><th>Severity</th><th>V</th><th>I</th><th>T</th><th>Fault</th></tr>';
    data.events.slice().reverse().forEach(e => {
      const color = e.severity==='CRITICAL'?'#fef2f2':e.severity==='WARNING'?'#fffbeb':'#f0fdf4';
      const tc = e.severity==='CRITICAL'?'#dc2626':'#d97706';
      html += `<tr style="background:${color};border-bottom:1px solid #f1f5f9;">
        <td style="padding:4px 6px;font-size:0.68rem;color:#64748b">${e.timestamp.slice(11)}</td>
        <td style="color:${tc};font-weight:700;font-size:0.68rem">${e.severity}</td>
        <td style="font-size:0.68rem">${e.voltage_v}V</td>
        <td style="font-size:0.68rem">${e.current_a}A</td>
        <td style="font-size:0.68rem">${e.temperature_c}°C</td>
        <td style="font-size:0.65rem;color:#64748b;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${e.faults}">${e.faults||'—'}</td>
      </tr>`;
    });
    html += '</table>';
    table.innerHTML = html;
  } catch(e) {}
}

function downloadCSV() { window.open('/api/log/csv','_blank'); }
async function clearLog() {
  await fetch('/api/log/clear',{method:'POST'});
  refreshLog();
}

window.addEventListener('load', ()=>{
  setTimeout(()=>runDiagnosis(), 400);
  resetCountdown();
  setInterval(fetchLiveSensors, 1000);
  setInterval(refreshLog, 10000);
  setTimeout(refreshLog, 3000);
});
</script>
</body>
</html>
"""

# Inject logo
if LOGO_B64:
    HTML = HTML.replace('LOGO_PLACEHOLDER', f'<img src="{LOGO_B64}" class="header-logo" alt="MotorMind AI">')
else:
    HTML = HTML.replace('LOGO_PLACEHOLDER', '<div class="header-logo-placeholder">⚙</div>')

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/sensors", methods=["POST"])
def api_sensors():
    data = request.get_json() or {}
    reading = simulate_motor(
        load_pct           = float(data.get("load_pct", 70)),
        voltage_v          = float(data.get("voltage_v", 400)),
        rpm_setpoint       = float(data.get("rpm_setpoint", 1450)),
        fault_bearing      = bool(data.get("fault_bearing", False)),
        fault_overtemp     = bool(data.get("fault_overtemp", False)),
        fault_overcurrent  = bool(data.get("fault_overcurrent", False)),
        fault_voltage_drop = bool(data.get("fault_voltage_drop", False)),
        noise=True,
    )
    with _state_lock:
        _latest_state.update({
            "voltage_v":      reading["voltage_v"],
            "current_a":      reading["current_a"],
            "temperature_c":  reading["temperature_c"],
            "vibration_mm_s": reading["vibration_mm_s"],
            "rpm":            reading["rpm"],
            "power_kw":       reading["power_kw"],
            "status":         reading["status"],
            "timestamp":      reading["timestamp"],
        })
    return jsonify(reading)

@app.route("/api/diagnose", methods=["POST"])
def api_diagnose():
    data = request.get_json() or {}
    result = run_diagnosis(
        load_pct           = float(data.get("load_pct", 70)),
        voltage_v          = float(data.get("voltage_v", 400)),
        rpm_setpoint       = float(data.get("rpm_setpoint", 1450)),
        fault_bearing      = bool(data.get("fault_bearing", False)),
        fault_overtemp     = bool(data.get("fault_overtemp", False)),
        fault_overcurrent  = bool(data.get("fault_overcurrent", False)),
        fault_voltage_drop = bool(data.get("fault_voltage_drop", False)),
    )
    log_fault_event(result)
    # Keep latest state in sync for UiPath polling
    s = result.get("sensors", {})
    with _state_lock:
        _latest_state.update({
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
    return jsonify(result)


@app.route("/api/latest", methods=["GET"])
def api_latest():
    """
    UiPath BPMN Script task GETs this when a process starts.
    Returns live sensor values + severity so the Agent task has real inputs.
    """
    with _state_lock:
        return jsonify(dict(_latest_state))


@app.route("/api/uipath/trigger", methods=["POST"])
def api_uipath_trigger():
    """
    UiPath calls this to trigger a full diagnosis from BPMN.
    Same as /api/diagnose but accepts the 7 UiPath agent input fields directly.
    Returns severity + diagnosis + bpmn_route for gateway routing.
    """
    data = request.get_json(force=True, silent=True) or {}
    # Accept either fault-injection params OR raw sensor values
    if "fault_bearing" in data or "load_pct" in data:
        result = run_diagnosis(
            load_pct           = float(data.get("load_pct", 70)),
            voltage_v          = float(data.get("voltage_v", 400)),
            rpm_setpoint       = float(data.get("rpm_setpoint", 1450)),
            fault_bearing      = bool(data.get("fault_bearing", False)),
            fault_overtemp     = bool(data.get("fault_overtemp", False)),
            fault_overcurrent  = bool(data.get("fault_overcurrent", False)),
            fault_voltage_drop = bool(data.get("fault_voltage_drop", False)),
        )
    else:
        # Called with live sensor values from the web dashboard
        with _state_lock:
            snap = dict(_latest_state)
        result = run_diagnosis(voltage_v=snap["voltage_v"])
    log_fault_event(result)
    return jsonify(result)

@app.route("/api/log")
def api_log():
    """Return the fault log as JSON."""
    return jsonify({"count": len(fault_log), "events": fault_log[-50:]})

@app.route("/api/log/csv")
def api_log_csv():
    """Download the fault log as CSV."""
    if not fault_log:
        return "No fault events logged yet.", 200
    fields = ["timestamp","severity","status","voltage_v","current_a",
              "temperature_c","vibration_mm_s","rpm","power_kw","faults","ai_status","ai_risk","bpmn_route"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(fault_log)
    csv_content = output.getvalue()
    from flask import Response
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=motormind_fault_log.csv"}
    )

@app.route("/api/log/clear", methods=["POST"])
def api_log_clear():
    fault_log.clear()
    return jsonify({"status": "cleared"})

@app.route("/api/chat", methods=["POST"])
def api_chat():
    import urllib.request, urllib.error
    data     = request.get_json() or {}
    user_msg = data.get("message","")
    last_res = data.get("last_result")
    hist     = data.get("history",[])

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY","")
    GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
                  f"gemini-3.1-flash-lite:generateContent?key={GEMINI_API_KEY}")

    ctx = ""
    if last_res:
        s = last_res.get("sensors",{})
        ctx = (f"MOTOR STATE: Severity={last_res.get('severity')} Status={last_res.get('status')}\n"
               f"Voltage={s.get('voltage_v')}V Current={s.get('current_a')}A "
               f"Temp={s.get('temperature_c')}C Vib={s.get('vibration_mm_s')}mm/s RPM={s.get('rpm')}\n"
               f"Faults: {last_res.get('fault_list',[])}\n")
        d = last_res.get("diagnosis",{})
        if d and not d.get("error"):
            ctx += f"AI: Status={d.get('status','')} Risk={d.get('risk','')}\n"
    if hist:
        ctx += f"\nHISTORY ({len(hist)} readings):\n"
        for i,r in enumerate(hist):
            ctx += f"  [{i+1}] V={r.get('voltage_v')} I={r.get('current_a')} T={r.get('temperature_c')} Vib={r.get('vibration_mm_s')} RPM={r.get('rpm')}\n"

    system = (
        "You are MotorMind AI, a senior motor diagnostic agent. "
        "MOTOR NAMEPLATE: 400V / 7.5kW / 1450 RPM / 15.2A rated current / PF=0.85 / Class F insulation / 91% efficiency. "
        "OPTIMAL OPERATING POINT: Voltage=400V, Current=10-15.2A (70-100% load), Temperature=55-75C, Vibration<2.5mm/s, RPM=1380-1450. "
        "NORMAL RANGES: Voltage 380-420V (below 360V=warning, below 340V=critical, above 420V=overvoltage warning), "
        "Current below 15.2A at full load (IMPORTANT: current below 15.2A is NORMAL — 15.2A is the MAXIMUM rated, not the target. "
        "At 70% load expect ~10A, at 100% load expect ~15.2A. Current is only a problem when it EXCEEDS 15.2A), "
        "Temperature 40-75C normal (above 80C=warning, above 100C=critical), "
        "Vibration below 2.5mm/s ideal, below 4.5mm/s acceptable ISO 10816, above 7.1mm/s=critical. "
        "EFFICIENCY DEGRADATION RULE: only flag if current exceeds what the load percentage predicts by more than 25%. "
        "Do NOT flag current as high if it is below 15.2A — that is normal motor operation. "
        "Use history to detect trends. Structure response with sections: "
        "STATUS:, ANALYSIS:, ACTIONS:, RISK: each on its own line. "
        "Under ACTIONS use Action 1:, Action 2: format. "
        "Keep each section 2-3 sentences. Plain text only, no markdown."
    )

    try:
        payload = json.dumps({
            "system_instruction": {"parts":[{"text":system}]},
            "contents": [{"role":"user","parts":[{"text":ctx+"\nQuestion: "+user_msg}]}],
            "generationConfig": {"temperature":0.2,"maxOutputTokens":600},
        }).encode()
        req = urllib.request.Request(GEMINI_URL, data=payload, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            r = json.loads(resp.read().decode())
            response = r["candidates"][0]["content"]["parts"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        response = "Rate limit — wait 60s." if e.code==429 else f"API error {e.code}: {body[:100]}"
    except Exception as e:
        response = f"Connection error: {e}"

    return jsonify({"response": response})

@app.route("/health")
def health():
    return jsonify({"status":"ok","agent":"MotorMind AI"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  MotorMind AI → http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
