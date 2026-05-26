# CrisisSwarm

**Microsoft Build AI Hackathon 2026** · **Theme 05 — Agent Swarms**

CrisisSwarm is a multi-agent disaster response system. A single model cannot safely triage casualties, allocate ambulances, plan routes, and broadcast alerts at once. Instead, **specialized agents** share one **situation brief** and pass structured outputs through a coordinated pipeline powered by **Groq (Llama 3.3)**.

## Features

- **Shared situation parsing** — disaster type, zones, blocked routes, hospitals, priorities
- **Six specialist agents** — Commander, Triage, Resource, Routing, Comms, Reporter
- **Final operational analysis** — risks, priority zones, recommended actions
- **Streamlit dashboard** — live agent transcript, metrics, downloadable SitRep
- **Docker-ready** — `docker-compose up` for judges and teammates
- **Offline fallbacks** — heuristics if Groq is unavailable (demo still runs)

## Architecture

Agents run **sequentially** with a shared `SwarmContext` (scenario + parsed situation). Each step calls Groq when `GROQ_API_KEY` is valid; otherwise deterministic fallbacks apply.

```mermaid
flowchart LR
    A[Scenario] --> B[Situation Parser]
    B --> C[Commander + Triage]
    C --> D[Resource]
    D --> E[Routing]
    E --> F[Comms]
    F --> G[Analysis]
    G --> H[Reporter]
    H --> I[Dashboard]
```

| Agent | Role |
|-------|------|
| **Situation** | Structured parse of the alert (zones, hazards, blocked roads) |
| **Triage** | Per-zone casualties + Critical / Serious / Minor |
| **Commander** | Task assignments and zone priority |
| **Resource** | Ambulances, medical teams, shelters, supplies |
| **Routing** | ETAs and deployment order (haversine + LLM adjustments) |
| **Comms** | Responder, hospital, and public alerts |
| **Analysis** | Cross-agent synthesis and next actions |
| **Reporter** | Executive situation report |

## Tech stack

| Tool | Use |
|------|-----|
| [Groq API](https://console.groq.com/) | Llama 3.3 70B for all agent reasoning |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | Groq-compatible chat client |
| [Streamlit](https://streamlit.io/) | Operations dashboard |
| [Docker](https://www.docker.com/) | Containerized demo |
| Azure Maps *(optional)* | `AZURE_MAPS_KEY` reserved for future route API integration |

## Project structure

```
crisisswarm/
├── agents/           # Commander, Triage, Resource, Routing, Comms, Reporter
├── core/             # Swarm orchestration, Groq client, situation parser
├── dashboard/        # Streamlit UI
├── config.py         # Environment settings
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example      # Copy to .env (not committed)
└── test_run_swarm.py
```

## Quick start (local)

### Prerequisites

- Python 3.11+ (3.13 supported)
- [Groq API key](https://console.groq.com/keys)

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/crisisswarm.git
cd crisisswarm
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
```

> **Never commit `.env`** — it is listed in `.gitignore`. Only commit `.env.example` with placeholders.

### 3. Verify Groq

```bash
python -c "from core.groq_client import verify_connection; print(verify_connection())"
```

Expected: `(True, 'Connected ...')`

### 4. Run

**Dashboard (recommended for demo):**

```bash
streamlit run dashboard/app.py
```

Open [http://localhost:8501](http://localhost:8501) → **ACTIVATE SWARM**.

**CLI test:**

```bash
python test_run_swarm.py
```

**Full agent chain:**

```bash
python run_full_demo.py
```

## Docker

```bash
cp .env.example .env
# Add your GROQ_API_KEY to .env

docker-compose up --build
```

UI: [http://localhost:8501](http://localhost:8501)

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes (for AI mode) | Groq API secret |
| `GROQ_MODEL` | No | Default: `llama-3.3-70b-versatile` |
| `AZURE_MAPS_KEY` | No | Optional maps integration |
| `STREAMLIT_PORT` | No | Default: `8501` |
| `SERVICE_NAME` | No | Display name |

## Push to GitHub

1. Create a new repository on GitHub (empty, no README if you already have one locally).

2. From the project root:

```bash
git add .
git status
```

Confirm **`.env` does not appear** in `git status`. If it does:

```bash
git rm --cached .env
```

3. Commit and push:

```bash
git commit -m "CrisisSwarm: Groq multi-agent disaster response pipeline"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/crisisswarm.git
git push -u origin main
```

### Security checklist before push

- [ ] `.env` is **not** staged (only `.env.example`)
- [ ] No API keys in source code, README, or commit history
- [ ] Rotate any key that was ever pasted in chat or committed by mistake

## Team

- **Tejas** — AI architecture, agent pipeline, Groq integration
- *[Add teammate names and roles]*

## License

Add a `LICENSE` file (e.g. MIT) if required by the hackathon.

## Hackathon demo tips

1. Show **Groq live** banner on the dashboard.
2. Run the built-in Mumbai earthquake scenario.
3. Walk through the **conversation log** agent by agent.
4. Show **Operational Analysis** and download the JSON report.
5. Optional: show Groq console **API usage** increasing during the demo.

---

Built for emergency dispatch scenarios where speed, specialization, and structured coordination matter more than a single monolithic LLM reply.
