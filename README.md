# CrisisSwarm

**Microsoft Build AI Hackathon 2026** · **Theme 05 — Agent Swarms**

**Repository:** [github.com/tejaspatel2255/Mircosoft-crisisswarm](https://github.com/tejaspatel2255/Mircosoft-crisisswarm)

CrisisSwarm is a multi-agent disaster response system. Specialized agents share one **situation brief**, pass structured JSON downstream, and a **Verifier** double-checks the plan before the final SitRep is published. Intelligence is powered by **Groq (Llama 3.3 70B)** with offline fallbacks for resilient demos.

## Features

- **Shared situation parsing** — disaster type, zones, blocked routes, hospitals, priorities
- **Seven specialist agents** — Commander, Triage, Resource, Routing, Comms, **Verifier**, Reporter
- **Cross-agent analysis** — risks, priority zones, recommended actions
- **pydeck map** — Mumbai and Florida scenarios with color-coded triage zones and route ETAs
- **Azure Maps routing** — live route API when `AZURE_MAPS_KEY` is set; haversine fallback otherwise
- **Agent execution trace** — per-step model, latency (ms), Groq vs offline mode
- **Streamlit dashboard** — Operations, Map View, and Agent Trace tabs
- **Docker-ready** — `docker-compose up` for judges and teammates

## Architecture

Agents run **sequentially** with a shared `SwarmContext`. Each step calls Groq when `GROQ_API_KEY` is valid; deterministic fallbacks apply on failure.

```mermaid
flowchart LR
    A[Scenario] --> B[Situation Parser]
    B --> C[Commander + Triage]
    C --> D[Resource]
    D --> E[Routing]
    E --> F[Comms]
    F --> V[Verifier]
    V --> G[Analysis]
    G --> H[Reporter]
    H --> I[Dashboard]
```

### 30-second: How agents collaborate

1. **Situation** reads the raw alert and builds a structured brief (zones, blocked roads, severity).
2. **Triage** classifies casualties per zone (Critical / Serious / Minor) using that brief.
3. **Commander** turns triage into prioritized task assignments.
4. **Resource** allocates ambulances, teams, and shelters.
5. **Routing** computes ETAs (Azure Maps if configured, else haversine) and deployment order.
6. **Comms** drafts responder, hospital, and public alerts.
7. **Verifier** reviews all outputs — flags issues, suggests corrections, approves or blocks.
8. **Analysis** synthesizes the full operation; **Reporter** publishes the executive SitRep.

## Agent roles

| Agent | Role |
|-------|------|
| **Situation** | Structured parse of the alert |
| **Triage** | Per-zone casualties + severity breakdown |
| **Commander** | Task assignments and zone priority |
| **Resource** | Ambulances, medical teams, shelters |
| **Routing** | Azure Maps or haversine ETAs + LLM adjustments |
| **Comms** | Multi-audience alerts |
| **Verifier** | Consistency check, approval, confidence score |
| **Analysis** | Operational synthesis |
| **Reporter** | Executive situation report |

## Tech stack

| Tool | Use |
|------|-----|
| [Groq API](https://console.groq.com/) | Llama 3.3 70B for all agent reasoning |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | Groq-compatible chat client |
| [Streamlit](https://streamlit.io/) | Operations dashboard (3 tabs) |
| [pydeck](https://deckgl.readthedocs.io/) | Interactive zone map with triage colors |
| [Azure Maps Route API](https://learn.microsoft.com/azure/azure-maps/) | Live driving routes when key is set |
| [Docker](https://www.docker.com/) | Containerized demo |

## Project structure

```
crisisswarm/
├── agents/
│   ├── commander.py
│   ├── triage.py
│   ├── resource.py
│   ├── routing.py      # Azure Maps + haversine
│   ├── comms.py
│   ├── verifier.py     # NEW — reviews swarm outputs
│   └── reporter.py
├── core/
│   ├── swarm.py        # Pipeline orchestrator
│   ├── groq_client.py
│   ├── situation.py
│   ├── context.py
│   ├── analysis.py
│   └── scenario.py     # Mumbai + Florida scenarios
├── dashboard/
│   └── app.py          # Operations · Map · Agent Trace
├── config.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Quick start (local)

### Prerequisites

- Python 3.11+ (3.13 supported)
- [Groq API key](https://console.groq.com/keys)
- Optional: [Azure Maps key](https://azure.microsoft.com/products/azure-maps)

### 1. Clone and install

```bash
git clone https://github.com/tejaspatel2255/Mircosoft-crisisswarm.git
cd Mircosoft-crisisswarm
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
AZURE_MAPS_KEY=your_azure_maps_key_here   # optional
```

> **Never commit `.env`** — it is in `.gitignore`.

### 3. Verify Groq

```bash
python -c "from core.groq_client import verify_connection; print(verify_connection())"
```

### 4. Run

```bash
streamlit run dashboard/app.py
```

Open [http://localhost:8501](http://localhost:8501):

1. Click **Mumbai Earthquake** or **Florida Hurricane**
2. Click **ACTIVATE SWARM**
3. Review **Operations**, **Map View**, and **Agent Trace** tabs

**CLI:**

```bash
python test_run_swarm.py
```

## Docker

```bash
cp .env.example .env
# Add GROQ_API_KEY to .env

docker-compose up --build
```

UI: [http://localhost:8501](http://localhost:8501)

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes (for AI) | Groq API secret |
| `GROQ_MODEL` | No | Default: `llama-3.3-70b-versatile` |
| `AZURE_MAPS_KEY` | No | Enables Azure Maps Route API in Routing agent |
| `STREAMLIT_PORT` | No | Default: `8501` |

## Demo video

<!-- Replace with your submitted demo link -->
🎬 **Demo video:** _[Add YouTube / Drive link here before submission]_

Suggested flow (2–3 min):

1. Show **Groq live** banner and **Agent Trace** tab
2. Run **Mumbai Earthquake** → walk the conversation log
3. Switch to **Map View** — colored zones + ETAs
4. Run **Florida Hurricane** — same pipeline, different geography
5. Highlight **Verifier** approval and confidence score
6. Show Groq console API usage increasing

## Push to GitHub

```bash
git add .
git status   # confirm .env is NOT listed
git commit -m "feat: verifier, map, Azure Maps routing, agent trace"
git push origin main
```

## Team

- **Tejas** — AI architecture, agent pipeline, Groq integration

## License

MIT (add `LICENSE` file if required by the hackathon).

---

Built for emergency dispatch where **specialization**, **verification**, and **structured coordination** beat a single monolithic LLM reply.
