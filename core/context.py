"""Shared context passed between CrisisSwarm agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json


@dataclass
class SwarmContext:
    """Accumulates scenario understanding and agent outputs across the pipeline."""

    scenario_text: str
    situation: Dict[str, Any] = field(default_factory=dict)
    agent_log: List[Dict[str, str]] = field(default_factory=list)

    def add_log(self, agent: str, message: str) -> None:
        self.agent_log.append({"agent": agent, "message": message})

    def situation_summary(self) -> str:
        if not self.situation:
            return self.scenario_text
        return json.dumps(self.situation, indent=2)

    def prompt_block(self, extra: str = "") -> str:
        """Standard context block for Groq agent prompts."""
        parts = [
            "=== DISASTER SCENARIO ===",
            self.scenario_text,
            "=== PARSED SITUATION (structured) ===",
            self.situation_summary(),
        ]
        if extra:
            parts.extend(["=== ADDITIONAL INPUT ===", extra])
        return "\n".join(parts)
