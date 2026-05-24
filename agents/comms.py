"""Comms Agent for CrisisSwarm.

Simulates broadcasting alerts to responders, hospitals, and families.
Replace the stubbed `send_alerts` with Azure Communication Services or
another provider for real delivery in production. Returns a structured
delivery log for auditing and UI display.
"""
from typing import List, Dict, Any
import json
import time
import traceback

AGENT_NAME = "Comms"

SYSTEM_MESSAGE = (
    "Comms Agent (Communications): Broadcast alerts to responders, hospitals, "
    "and families. For each message provide recipient_type, contact, message, "
    "and delivery status. Ensure messages are concise and include action items.\n"
    "Output format: {agent, system_message, delivery_log: [...] }"
)


def send_alerts(delivery_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simulate sending alerts and return a delivery log.

    Args:
        delivery_items: list of dicts with `recipient_type`, `contact`, and `message`.

    Returns:
        dict with `agent`, `system_message`, and `delivery_log`.
    """
    print("[Comms] Preparing to send alerts")
    try:
        log = []
        for item in delivery_items:
            recipient = item.get("recipient_type", "unknown")
            contact = item.get("contact")
            message = item.get("message", "")
            time.sleep(0.05)
            status = "sent" if message else "failed"
            entry = {"recipient_type": recipient, "contact": contact, "message": message, "status": status}
            print(f"[Comms] -> {recipient}: {status}")
            log.append(entry)

        output = {"agent": AGENT_NAME, "system_message": SYSTEM_MESSAGE, "delivery_log": log}
        print(f"[Comms] Delivery log for {AGENT_NAME}:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Comms] Error sending alerts: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point for orchestrators; expects `message` with `alerts` key."""
    items = message.get("alerts", [])
    return send_alerts(items)


if __name__ == "__main__":
    items = [{"recipient_type": "responder", "contact": None, "message": "Deploy to Dharavi"}]
    send_alerts(items)
