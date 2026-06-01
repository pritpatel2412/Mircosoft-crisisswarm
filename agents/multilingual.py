"""Multi-language emergency voice/text announcements (demo-ready)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.context import SwarmContext

AGENT_NAME = "MultilingualAgent"

# Template strings per language (offline; plug Azure Speech / Sarvam in production)
_TEMPLATES = {
    "en": "Attention residents of {zone}. Proceed to Shelter Point {shelter}. Medical assistance is available.",
    "hi": "ध्यान दें {zone} के निवासियों। शेल्टर पॉइंट {shelter} पर जाएं। चिकित्सा सहायता उपलब्ध है।",
    "mr": "लक्ष {zone} रहिवाशांना: शेल्टर पॉइंट {shelter} कडे जा. वैद्यकीय मदत उपलब्ध आहे.",
    "gu": "ધ્યાન {zone} ના રહેવાસીઓ. શેલ્ટર પોઇન્ટ {shelter} પર જાઓ. તબીબી સહાય ઉપલબ્ધ છે.",
    "ta": "கவனிக்கவும் {zone} குடியிருப்பாளர்களே. தஞ்சமிடம் {shelter} செல்லுங்கள். மருத்துவ உதவி கிடைக்கும்.",
}


def generate_multilingual_alerts(
    plan: Dict[str, Any],
    comms: Optional[Dict[str, Any]] = None,
    context: Optional[SwarmContext] = None,
) -> Dict[str, Any]:
    """Produce emergency announcements in multiple languages."""
    zones = list(plan.get("triage", {}).get("zones", {}).keys()) or ["affected area"]
    announcements: List[Dict[str, Any]] = []

    for i, zone in enumerate(zones[:3]):
        shelter_id = chr(65 + i)
        for lang, template in _TEMPLATES.items():
            text = template.format(zone=zone, shelter=shelter_id)
            announcements.append({
                "zone": zone,
                "language": lang,
                "text": text,
                "tts_provider": "azure_speech|sarvam|elevenlabs",
                "status": "ready_for_synthesis",
            })

    output = {
        "agent": AGENT_NAME,
        "languages": list(_TEMPLATES.keys()),
        "announcements": announcements,
        "integration_note": (
            "Connect GROQ/Azure Speech/Sarvam API keys to synthesize audio in demo."
        ),
        "llm_used": False,
    }
    if context:
        context.add_log(AGENT_NAME, f"Generated {len(announcements)} multilingual alerts")
    return output
