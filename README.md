---

### SECTION 1 — Hero Banner
🚨 CrisisSwarm — Multi-Agent Disaster Response
Microsoft Build AI Hackathon 2026 · Theme 05 — Agent Swarms

"8 specialized AI agents coordinate disaster response in real time — each with one job, shared situational awareness, and a verifier that challenges the plan before alerts are broadcast."

---

### SECTION 2 — Live Demo box
🚀 Live Demo
👉 https://mircosoft-crisisswarm-n6uhmu7uk2wnesmxddv6dq.streamlit.app

Select a scenario → click ACTIVATE SWARM → watch 8 agents coordinate in real time.

---

### SECTION 3 — 30-Second How It Works
One dispatcher cannot safely triage, allocate, route, and broadcast at once. CrisisSwarm deploys 8 specialized agents sharing one situation brief. Each agent produces structured JSON passed to the next. A Verifier agent cross-checks all outputs before Comms broadcasts. Human operator reviews and approves the plan at a checkpoint. Powered by Groq Llama 3.3 70B for sub-second agent steps.

---

### SECTION 4 — Features list
- Shared situation parsing — disaster type, zones, blocked routes, hospitals, priorities extracted by Groq
- 8 specialist agents — Situation, Commander, Triage, Resource, Routing, Comms, Verifier, Reporter
- Verifier agent — cross-checks all outputs, returns issues found, approved true/false, confidence score 0-100
- Human approval checkpoint — operator reviews triage + routing plan before Comms broadcasts alerts
- Dual Groq key rotation — auto-switches to backup key on rate limit, circular and infinite
- 5 built-in disaster scenarios — Mumbai Earthquake, Florida Hurricane, Tokyo Flood, Turkey Earthquake, Chennai Cyclone
- Custom scenario support — type any disaster text, agents handle events they have never seen before
- Interactive map — zone markers colored by severity (red/orange/green), auto-zoom per scenario, ETA tooltips
- Real routing — Azure Maps Route API when key is set, haversine fallback always available
- PDF + JSON export — download full SitRep after every run
- Streamlit dashboard — live agent transcript, metrics, agent trace panel showing model + latency per step
- Docker-ready — docker-compose up for judges and teammates
- Offline fallbacks — deterministic heuristics if Groq unavailable, demo always runs

---

### SECTION 5 — Architecture
```text
Scenario Text
↓
[Situation Parser] — extracts zones, hazards, blocked roads
↓
[Commander + Triage] — task assignments + per-zone casualties
↓
[Resource] — ambulances, medical teams, supplies
↓
[Routing] — ETAs, deployment order, road status
↓
⚠️  HUMAN APPROVAL CHECKPOINT
↓
[Comms] — responder, hospital, public alerts
↓
[Verifier] — cross-checks ALL outputs, flags issues
↓
[Analysis] — cross-agent synthesis, recommended actions
↓
[Reporter] — executive SitRep
↓
[Dashboard] — map, transcript, PDF/JSON export
```

| Agent | Role |
|---|---|
| Situation | Structured parse — zones, hazards, blocked roads |
| Commander | Task assignments and zone priority |
| Triage | Per-zone casualties: Critical / Serious / Minor |
| Resource | Ambulances, medical teams, shelters, supplies |
| Routing | ETAs, deployment order (Azure Maps + haversine) |
| Comms | Responder, hospital, and public alerts |
| Verifier | Cross-checks all outputs, confidence score |
| Analysis | Synthesis, key risks, recommended actions |
| Reporter | Executive situation report |

---

### SECTION 6 — Tech Stack table
| Tool | Use |
|---|---|
| Groq API (Llama 3.3 70B) | All agent reasoning, sub-second inference |
| OpenAI Python SDK | Groq-compatible chat client |
| Streamlit | Operations dashboard |
| pydeck | Interactive zone map with severity colors |
| Azure Maps Route API | Real road routing (haversine fallback) |
| reportlab | PDF SitRep export (HTML fallback if not installed) |
| Docker | Containerized demo |
| Python 3.13 | Runtime |

---

### SECTION 7 — Project Structure
```text
crisisswarm/
├── agents/
│   ├── commander.py   # Commander + Triage
│   ├── resource.py    # Resource allocation
│   ├── routing.py     # Azure Maps + haversine routing
│   ├── comms.py       # Alert broadcasting
│   ├── verifier.py    # Cross-agent verification
│   └── reporter.py    # SitRep generation
├── core/
│   ├── swarm.py       # Orchestration pipeline
│   ├── scenario.py    # 5 scenarios + coord maps
│   ├── groq_client.py # Dual key rotation
│   ├── situation.py   # Situation parser
│   ├── context.py     # SwarmContext
│   └── analysis.py    # Operational analysis
├── dashboard/
│   └── app.py         # Streamlit UI
├── config.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

### SECTION 8 — Quick Start (local)
Prerequisites:
- Python 3.11+ (3.13 supported)
- Groq API key (https://console.groq.com/keys)

Steps:
1. Clone and install
   ```bash
   git clone https://github.com/tejaspatel2255/Mircosoft-crisisswarm.git
   cd Mircosoft-crisisswarm
   python -m venv venv
   source venv/bin/activate  # on Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Configure environment
   ```bash
   cp .env.example .env
   # Edit .env and add your GROQ_API_KEY
   ```
3. Optional: add GROQ_API_KEY_2 for dual key rotation
4. Optional: add AZURE_MAPS_KEY for real road routing
5. Verify Groq connection
   ```bash
   python -c "from core.groq_client import verify_connection; print(verify_connection())"
   ```
6. Run dashboard: `streamlit run dashboard/app.py`
7. Open http://localhost:8501

---

### SECTION 9 — Docker
To run with Docker:
```bash
docker-compose up --build
```
Then open http://localhost:8501 in your browser.

---

### SECTION 10 — Environment Variables table
| Variable | Required | Description |
|---|---|---|
| GROQ_API_KEY | Yes | Primary Groq API key |
| GROQ_API_KEY_2 | No | Backup key — auto-rotates on rate limit |
| GROQ_MODEL | No | Default: llama-3.3-70b-versatile |
| AZURE_MAPS_KEY | No | Real road routing (haversine if not set) |
| STREAMLIT_PORT | No | Default: 8501 |

---

### SECTION 11 — 5 Scenarios
| Scenario | Location | Event | Zones |
|---|---|---|---|
| Mumbai Earthquake | Mumbai, India | 6.8 magnitude | Dharavi, Kurla, Andheri |
| Florida Hurricane | Miami, USA | Category 4 | Downtown, South Beach, Little Havana, Coral Gables |
| Tokyo Flood | Tokyo, Japan | Typhoon flash flood | Koto, Edogawa, Sumida |
| Turkey Earthquake | Kahramanmaras | 7.4 magnitude | City Centre, Dulkadiroglu, Onikisibat, Pazarcik |
| Chennai Cyclone | Chennai, India | Cyclone Vayu | Marina, Adyar, Tambaram |

*Or type any custom disaster scenario — agents handle events they have never seen before.*

---

### SECTION 12 — Security checklist
- [ ] .env is NOT staged (only .env.example)
- [ ] No API keys in source code or commit history
- [ ] Rotate any key that was ever pasted in chat or committed

---

### SECTION 13 — Team
- Tejas Patel — AI architecture, agent pipeline, Groq integration, Streamlit dashboard
- [Add teammate names and roles]

---

### SECTION 14 — License
MIT License

---

### SECTION 15 — Hackathon pitch line (last line of README)
> "CrisisSwarm deploys 8 specialized agents that share situational awareness, verify each other's outputs, and wait for human approval before broadcasting — powered by Groq for real-time inference."
