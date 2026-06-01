"""Crisis Replay — timeline of digital-twin snapshots for playback."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class CrisisReplay:
    """Records world state after each agent step for dashboard playback."""

    def __init__(self) -> None:
        self.frames: List[Dict[str, Any]] = []

    def capture(
        self,
        step: str,
        world_dict: Dict[str, Any],
        detail: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.frames.append({
            "index": len(self.frames),
            "step": step,
            "tick": world_dict.get("tick", 0),
            "detail": detail,
            "world": world_dict,
            "extra": extra or {},
            "timestamp": time.time(),
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_count": len(self.frames),
            "frames": self.frames,
        }

    def frame_at(self, index: int) -> Optional[Dict[str, Any]]:
        if not self.frames:
            return None
        index = max(0, min(index, len(self.frames) - 1))
        return self.frames[index]

    def steps(self) -> List[str]:
        return [f.get("step", "") for f in self.frames]
