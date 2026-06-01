"""Disaster Digital Twin — stateful simulation world agents modify."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ZoneState:
    name: str
    casualties: int = 0
    critical: int = 0
    serious: int = 0
    minor: int = 0
    food: int = 0
    water: int = 0
    shelter: bool = False
    ambulances_deployed: int = 0
    medical_teams: int = 0
    access: str = "open"
    response_delay_min: int = 30

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "casualties": self.casualties,
            "critical": self.critical,
            "serious": self.serious,
            "minor": self.minor,
            "food": self.food,
            "water": self.water,
            "shelter": self.shelter,
            "ambulances_deployed": self.ambulances_deployed,
            "medical_teams": self.medical_teams,
            "access": self.access,
            "response_delay_min": self.response_delay_min,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ZoneState:
        return cls(
            name=data.get("name", "unknown"),
            casualties=int(data.get("casualties", 0)),
            critical=int(data.get("critical", 0)),
            serious=int(data.get("serious", 0)),
            minor=int(data.get("minor", 0)),
            food=int(data.get("food", 0)),
            water=int(data.get("water", 0)),
            shelter=bool(data.get("shelter", False)),
            ambulances_deployed=int(data.get("ambulances_deployed", 0)),
            medical_teams=int(data.get("medical_teams", 0)),
            access=str(data.get("access", "open")),
            response_delay_min=int(data.get("response_delay_min", 30)),
        )


class DisasterWorld:
    """
    Live simulation state for a disaster scenario.

    Agents read and mutate zone-level fields; metrics derive from deltas.
    """

    def __init__(
        self,
        disaster_type: str = "earthquake",
        tick: int = 0,
        global_resources: Optional[Dict[str, int]] = None,
    ):
        self.disaster_type = disaster_type
        self.tick = tick
        self.zones: Dict[str, ZoneState] = {}
        self.global_resources = global_resources or {
            "ambulances_available": 24,
            "medical_teams": 40,
        }
        self._initial_critical = 0
        self._history: List[Dict[str, Any]] = []

    def clone(self) -> DisasterWorld:
        """Deep copy for swarm arena runs."""
        other = DisasterWorld(
            disaster_type=self.disaster_type,
            tick=self.tick,
            global_resources=copy.deepcopy(self.global_resources),
        )
        other.zones = {k: ZoneState.from_dict(v.to_dict()) for k, v in self.zones.items()}
        other._initial_critical = self._initial_critical
        return other

    def to_dict(self) -> Dict[str, Any]:
        return {
            "disaster_type": self.disaster_type,
            "tick": self.tick,
            "zones": [z.to_dict() for z in self.zones.values()],
            "global_resources": self.global_resources,
            "metrics": self.compute_metrics(),
        }

    def _log(self, agent: str, action: str, detail: str = "") -> None:
        self._history.append({
            "tick": self.tick,
            "agent": agent,
            "action": action,
            "detail": detail,
        })

    @classmethod
    def from_situation(cls, situation: Dict[str, Any]) -> DisasterWorld:
        """Bootstrap twin from parsed situation brief."""
        world = cls(disaster_type=situation.get("disaster_type", "other"))
        for z in situation.get("zones", []):
            if not isinstance(z, dict):
                continue
            name = z.get("name", "unknown")
            cas = int(z.get("casualties", 0))
            crit = max(1, int(cas * 0.12)) if cas else 0
            ser = int(cas * 0.28) if cas else 0
            mino = max(0, cas - crit - ser)
            world.zones[name] = ZoneState(
                name=name,
                casualties=cas,
                critical=crit,
                serious=ser,
                minor=mino,
                food=max(5, cas // 20),
                water=max(5, cas // 25),
                shelter=False,
                access=str(z.get("access", "open")),
            )
        if not world.zones:
            world.zones["unknown"] = ZoneState(name="unknown", casualties=100, critical=10)
        world._initial_critical = sum(z.critical for z in world.zones.values())
        return world

    def apply_triage(self, triage: Dict[str, Any]) -> None:
        """Triage agent refines casualty classification."""
        self.tick += 1
        zones = triage.get("zones", {})
        for name, info in zones.items():
            if not isinstance(info, dict):
                continue
            z = self.zones.setdefault(name, ZoneState(name=name))
            br = info.get("breakdown") or {}
            z.casualties = int(info.get("estimated_total", z.casualties))
            z.critical = int(br.get("Critical", z.critical))
            z.serious = int(br.get("Serious", z.serious))
            z.minor = int(br.get("Minor", max(0, z.casualties - z.critical - z.serious)))
            self._log("Triage", "classify", f"{name}: {z.critical} critical")
        self._initial_critical = sum(z.critical for z in self.zones.values())

    def apply_resource(
        self,
        allocations: Dict[str, Any],
        strategy: str = "default",
    ) -> None:
        """Resource deployment reduces critical victims and consumes fleet."""
        self.tick += 1
        for alloc in allocations.get("allocations", []):
            if not isinstance(alloc, dict):
                continue
            zone = alloc.get("zone")
            if zone not in self.zones:
                continue
            z = self.zones[zone]
            amb = int(alloc.get("ambulances", 0))
            teams = int(alloc.get("medical_teams", 0))
            shelters = int(alloc.get("shelters", 0))

            if strategy == "medical_first":
                relief = min(z.critical, amb * 3 + teams)
            elif strategy == "resource_balanced":
                relief = min(z.critical, amb * 2 + teams // 2)
            else:
                relief = min(z.critical, amb * 2 + teams)

            z.critical = max(0, z.critical - relief)
            z.serious = max(0, z.serious - relief // 3)
            z.ambulances_deployed += amb
            z.medical_teams += teams
            if shelters > 0:
                z.shelter = True
                z.food += shelters * 10
                z.water += shelters * 15

            fleet = self.global_resources.get("ambulances_available", 24)
            self.global_resources["ambulances_available"] = max(0, fleet - amb)
            self._log("Resource", "deploy", f"{zone}: -{relief} critical, {amb} amb")

    def apply_routing(self, routes: Dict[str, Any]) -> None:
        """Routing updates per-zone response delay from ETAs."""
        self.tick += 1
        for route in routes.get("routes", []):
            if not isinstance(route, dict):
                continue
            zone = route.get("zone")
            if zone not in self.zones:
                continue
            eta = int(route.get("eta_minutes", 30))
            status = str(route.get("status", "ok")).lower()
            delay = eta if status == "ok" else eta + 20
            self.zones[zone].response_delay_min = delay
            self._log("Routing", "eta", f"{zone}: {delay} min")

    def apply_comms(self, comms: Dict[str, Any]) -> None:
        """Comms reduce coordination delay across zones."""
        self.tick += 1
        sent = len(comms.get("delivery_log", []))
        reduction = min(8, sent * 2)
        for z in self.zones.values():
            z.response_delay_min = max(5, z.response_delay_min - reduction)
        self._log("Comms", "broadcast", f"delay -{reduction} min")

    def apply_aftershock(self, event: Dict[str, Any]) -> None:
        """External event increases casualties (e.g. aftershock)."""
        self.tick += 1
        multiplier = float(event.get("casualty_multiplier", 1.15))
        extra_critical = int(event.get("extra_critical_per_zone", 5))
        for z in self.zones.values():
            added = max(1, int(z.casualties * (multiplier - 1)))
            z.casualties += added
            z.critical += extra_critical
            z.minor += max(0, added - extra_critical)
            z.access = event.get("access_override", z.access) or z.access
        self._log("Aftershock", "impact", event.get("label", "aftershock"))

    def compute_metrics(
        self,
        verification: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Leaderboard metrics from current world state."""
        current_critical = sum(z.critical for z in self.zones.values())
        lives_saved = max(0, self._initial_critical - current_critical)
        delays = [z.response_delay_min for z in self.zones.values()]
        avg_response = int(sum(delays) / len(delays)) if delays else 0

        sheltered = sum(1 for z in self.zones.values() if z.shelter)
        coverage = round(100 * sheltered / max(1, len(self.zones)), 1)

        total_cas = sum(z.casualties for z in self.zones.values())
        risk_score = round(
            100 * current_critical / max(1, total_cas),
            1,
        )

        feasibility = 1.0
        if verification:
            feasibility = float(verification.get("confidence_score", 1.0))

        mission_score = min(
            100,
            int(
                lives_saved * 1.2
                + (100 - min(avg_response, 100)) * 0.3
                + coverage * 0.2
                + feasibility * 20
            ),
        )

        return {
            "lives_saved": lives_saved,
            "response_time_min": avg_response,
            "coverage_pct": coverage,
            "risk_score": risk_score,
            "feasibility": round(feasibility, 2),
            "mission_score": mission_score,
            "critical_remaining": current_critical,
            "total_casualties": total_cas,
        }

    @property
    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)
