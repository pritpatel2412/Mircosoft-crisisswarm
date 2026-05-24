# CrisisSwarm

CrisisSwarm is a Multi-Agent Disaster Response System built for the Microsoft Build AI Hackathon 2026.
It uses Microsoft AutoGen, Semantic Kernel, Azure OpenAI, Azure Maps, and Streamlit to simulate a swarm of 6 coordinated agents handling disasters.

## Project Structure

- `agents/`
  - `commander.py` — Master orchestrator that delegates tasks to other agents.
  - `triage.py` — Classifies victims into Critical / Serious / Minor.
  - `resource.py` — Allocates ambulances, food, water, and medical teams.
  - `routing.py` — Finds safest routes using Azure Maps.
  - `comms.py` — Sends alerts to responders and families.
  - `reporter.py` — Generates situation reports every 15 minutes.
- `core/`
  - `swarm.py` — GroupChat orchestration for agent collaboration.
  - `scenario.py` — Disaster scenario loader and simulator.
- `dashboard/`
  - `app.py` — Streamlit dashboard UI for live conversation logs and status.
- `config.py` — Configuration loader (loads secrets from environment variables).
- `requirements.txt` — Python dependencies.

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file for your credentials:
   ```bash
   cp .env.example .env
   ```
4. Add your Azure credentials inside the newly created `.env` file.

## Next Step

Start by building `agents/commander.py` and `agents/triage.py` first, then test them talking to each other.

## Demo Scenario

Use this scenario to test the system:

"DISASTER ALERT: 6.8 magnitude earthquake struck Mumbai at 14:32 IST. Estimated 450 casualties across 3 zones: Dharavi (200), Kurla (150), Andheri (100). 8 buildings collapsed. Western Express Highway blocked. Bandra-Worli Sea Link operational. 12 hospitals on alert. Coordinate full emergency response immediately."

> Note: Run `streamlit run dashboard\app.py` after all files are complete.
