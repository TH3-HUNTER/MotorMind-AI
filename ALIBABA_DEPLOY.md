# MotorMind AI — Alibaba Cloud Deploy Guide
# Ubuntu 22.04 + Docker

---

## STEP 1 — Connect to your server

Windows PowerShell or CMD:
```
ssh root@YOUR_ALIBABA_IP
```
If you have a .pem key:
```
ssh -i C:\path\to\key.pem root@YOUR_ALIBABA_IP
```

---

## STEP 2 — Open port 5000 in Alibaba Security Group (do this first)

1. Alibaba Console → ECS → Your Instance → Security Groups → Add Rule (Inbound)
2. Protocol: TCP | Port: 5000/5000 | Source: 0.0.0.0/0
3. Click OK

Without this UiPath cloud can never reach your app.

---

## STEP 3 — Install Docker on Ubuntu 22.04

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl start docker
systemctl enable docker
docker --version
# Should print: Docker version 24.x or higher
```

---

## STEP 4 — Upload your project to the server

On your PC, open a NEW terminal (keep SSH open):

```bash
scp -r "C:\Users\hm971\Desktop\Hackathon Projects\MotoMind AI\MotoMind AI\." root@YOUR_ALIBABA_IP:/root/motormind/
```

With .pem key:
```bash
scp -i C:\path\to\key.pem -r "C:\Users\hm971\Desktop\Hackathon Projects\MotoMind AI\MotoMind AI\." root@YOUR_ALIBABA_IP:/root/motormind/
```

---

## STEP 5 — Create Dockerfile on the server

```bash
cd /root/motormind
nano Dockerfile
```

Paste this exactly:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir flask gunicorn

COPY . .

EXPOSE 5000

CMD ["gunicorn", "web_app:app", "--bind", "0.0.0.0:5000", "--timeout", "120", "--workers", "2"]
```

Save: Ctrl+O → Enter → Ctrl+X

---

## STEP 6 — Create requirements.txt

```bash
nano requirements.txt
```

Paste:
```
flask
gunicorn
```

Save: Ctrl+O → Enter → Ctrl+X

---

## STEP 7 — Build and run the Docker container

```bash
cd /root/motormind

# Build (takes 1-2 min first time)
docker build -t motormind-ai .

# Run permanently (restarts automatically on server reboot)
docker run -d \
  --name motormind \
  --restart always \
  -p 5000:5000 \
  -e GEMINI_API_KEY="AQ.Ab8RN6JtJVHhlQp6pWNqzsgZdiqZ9jK3yUzUwfm-wDH1vrL_dg" \
  motormind-ai

# Verify running
docker ps
# Should show: motormind   Up X seconds   0.0.0.0:5000->5000/tcp

# Check logs
docker logs motormind
```

---

## STEP 8 — Test it

Browser:
```
http://YOUR_ALIBABA_IP:5000          → full dashboard
http://YOUR_ALIBABA_IP:5000/health   → {"status":"ok"}
http://YOUR_ALIBABA_IP:5000/api/latest → live sensor JSON
```

---

## STEP 9 — Put this URL in UiPath

In your BPMN Script task, use:
```
http://YOUR_ALIBABA_IP:5000/api/latest
http://YOUR_ALIBABA_IP:5000/api/diagnose
```

Your Alibaba IP never resets. No ngrok needed.

---

## Update code after changes

PC → upload changed files:
```bash
scp web_app.py root@YOUR_ALIBABA_IP:/root/motormind/web_app.py
scp agent/motor_agent.py root@YOUR_ALIBABA_IP:/root/motormind/agent/motor_agent.py
```

Server → rebuild:
```bash
cd /root/motormind
docker stop motormind && docker rm motormind
docker build -t motormind-ai .
docker run -d --name motormind --restart always -p 5000:5000 \
  -e GEMINI_API_KEY="AQ.Ab8RN6JtJVHhlQp6pWNqzsgZdiqZ9jK3yUzUwfm-wDH1vrL_dg" \
  motormind-ai
```

---

## Useful commands

```bash
docker logs -f motormind        # live logs
docker restart motormind        # quick restart
docker stats motormind          # CPU/RAM usage
docker exec -it motormind bash  # open shell inside container
docker system prune -a          # free disk space (removes old images)
```

---

## Troubleshooting

**"Connection refused" in browser:**
→ Security group port 5000 not open (redo Step 2)
→ Container not running: docker ps (if empty, check docker logs motormind)

**"ModuleNotFoundError: No module named 'motor_agent'":**
→ File structure issue — check: docker exec -it motormind ls /app/agent/
→ Should show motor_agent.py. If not, verify your local folder has agent/motor_agent.py and re-upload.

**Gemini not responding:**
→ Check key set: docker exec -it motormind env | grep GEMINI
→ Should print your key. If empty, re-run docker run with -e flag.

**Container keeps restarting:**
→ docker logs motormind → read the error at the bottom
→ Usually a Python import error in web_app.py
