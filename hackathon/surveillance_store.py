"""
Surveillance data store — lightweight, runs in-process inside WebsocketVisModule.

Receives person sightings from PeopleMonitor and persists them to JSONL.
SurveillanceSkill (a Module in the blueprint) reads from the same files
to answer queries.
"""

from __future__ import annotations

import json
import os
import threading
import time

from dimos.utils.logging_config import setup_logger

logger = setup_logger()

DATA_DIR = os.path.join("assets", "surveillance")
OBS_FILE = os.path.join(DATA_DIR, "observations.jsonl")
ROSTER_FILE = os.path.join(DATA_DIR, "roster.json")

# Throttle: one observation per person per N seconds (unless activity changes)
MIN_OBS_INTERVAL = 5.0


class SurveillanceStore:
    """Persists people activity observations to disk."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._roster: dict[str, dict] = {}
        self._last_obs_ts: dict[str, float] = {}
        os.makedirs(DATA_DIR, exist_ok=True)
        self._obs_file = open(OBS_FILE, "a")  # noqa: SIM115
        # Load existing roster
        if os.path.exists(ROSTER_FILE):
            try:
                with open(ROSTER_FILE) as f:
                    self._roster = json.load(f)
                logger.info(f"SurveillanceStore: loaded {len(self._roster)} people from roster")
            except Exception:
                pass

    def on_person_sighting(self, sighting: dict) -> None:
        """Called for each person sighting. Throttles and persists."""
        pid = sighting.get("person_id", "")
        activity = sighting.get("activity", "detected")
        now = time.time()

        with self._lock:
            last_ts = self._last_obs_ts.get(pid, 0.0)
            last_activity = self._roster.get(pid, {}).get("activity", "")

            # Skip if same activity and too recent
            if activity == last_activity and (now - last_ts) < MIN_OBS_INTERVAL:
                return

            self._last_obs_ts[pid] = now
            self._roster[pid] = {
                "person_id": pid,
                "long_term_id": sighting.get("long_term_id"),
                "activity": activity,
                "first_seen": self._roster.get(pid, {}).get("first_seen", now),
                "last_seen": now,
            }

        # Append observation
        obs = {
            "ts": now,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "person_id": pid,
            "long_term_id": sighting.get("long_term_id"),
            "activity": activity,
        }
        try:
            self._obs_file.write(json.dumps(obs) + "\n")
            self._obs_file.flush()
        except Exception:
            pass

        # Save roster periodically (every sighting that passes throttle)
        self._save_roster()

    def _save_roster(self) -> None:
        try:
            with open(ROSTER_FILE, "w") as f:
                json.dump(self._roster, f, indent=2)
        except Exception:
            pass

    def stop(self) -> None:
        if self._obs_file:
            self._obs_file.close()
        self._save_roster()
