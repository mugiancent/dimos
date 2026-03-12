# Status — What's Done, What's Next

## Phase 1: Dashboard Shell — DONE

- [x] `mission_control.html` — dark 3-col grid layout
- [x] Routes: `/`, `/mission-control`, `/legacy`, `/command-center`, `/health`, `/api/services`
- [x] SocketIO connection status (green/yellow/red dot in header)
- [x] Auto-launch `dtop` via textual-serve
- [x] Clean shutdown of spy tool subprocesses
- [x] Rerun overlay (shows hint if Rerun not running)

## Phase 2: In-Process Monitors + Claude Chat — DONE

- [x] `AgentMessageMonitor` running in-process, streaming `agent_message` via SocketIO
- [x] `GraphLCMSpy` running in-process, streaming `lcm_stats` every 1s via SocketIO
- [x] Native LCM Stats panel (table with topic name, freq, bandwidth, total)
- [x] MCP Skills panel (polls `localhost:9990/mcp` every 15s, lists all tools)
- [x] Claude Chat panel (`/api/chat` → Claude opus with MCP tool-use, brief tool usage summary)
- [x] Light control skill (`light_skill.py` — Sonoff S31 smart plug via ESPHome)

## Phase 3: Skill Event Stream — DONE

- [x] Real-time `skill_invocation` SocketIO event from both LCM agent path and `/api/chat` HTTP path
- [x] Event payload: `{id, timestamp, name, args, status, result, duration_ms}`
- [x] Duration tracking: matches AIMessage tool_calls to ToolMessage responses by tool_call_id
- [x] Skills Feed panel: live log with timestamp, skill name, args, duration, status badge (RUN/OK/ERR)
- [x] Status updates in-place (running → success/error with duration)
- [x] Orphan tool messages handled gracefully (no crash if start event missed)
- [x] Claude Chat cleaned up: shows "Used: skill_name" instead of dumping raw results/base64
- [x] Tests: 40 tests in `hackathon/tests/test_skills_feed.py`

### Layout changes (Phase 3):
- Removed Command Center (2D map)
- Rerun 3D moved to full left column (rows 1-2)
- LCM Stats + dtop split side-by-side in bottom-left (row 3)
- Skills Feed (col2, row1), Claude (col2, row2), MCP Skills (col2, row3)
- Empty right column (col3, rows 1-3) — reserved for Phase 4

## Phase 4: People Intelligence — DONE

- [x] `PeopleMonitor` — subscribes to Detection2DModule (YOLO 2Hz) via LCM
- [x] Person ReID via OSNet (EmbeddingIDSystem) for persistent IDs across track resets
- [x] Activity classification per person crop via Claude Haiku (every 10s)
- [x] Dashboard panel: person cards in col3 — thumbnail, ID, activity, activity log, "Xs ago"
- [x] SocketIO streaming (`person_sighting` events) with rAF-throttled rendering
- [x] Blob URL management to prevent memory leaks, max 20 cards with LRU eviction
- [x] Bbox area filter (MIN_BBOX_AREA=2000) to reject small false positives
- [x] Tests: 40 tests in `hackathon/tests/test_people_monitor.py`

### Bugs fixed (Phase 4):
- ROS round-trip drops `name` field → filter by `class_id == 0` instead of `d.name == "person"`
- ROS round-trip drops `confidence` (always 0.00) → cannot filter by confidence
- PeopleMonitor logger (`hackathon.people_monitor`) not in DimOS config → use `setup_logger()`
- Image transport mismatch: blueprint uses LCMTransport, PeopleMonitor used pSHMTransport → fixed

## Phase 5: Surveillance Query Engine — DONE

- [x] `SurveillanceStore` — in-process, persists activity observations to `assets/surveillance/`
  - `observations.jsonl` — timestamped activity log (throttled: 1 per 5s or on activity change)
  - `roster.json` — current person states (ID, activity, first/last seen)
- [x] `SurveillanceSkill` — MCP-exposed Module with two skills:
  - `query_surveillance(question)` — answers natural-language questions via Claude Haiku + observation data
  - `list_people()` — returns current roster summary
- [x] Wired into WebsocketVisModule: PeopleMonitor → SurveillanceStore → disk ← SurveillanceSkill
- [x] Blueprint renamed: `unitree-go2-agentic-mcp-surveillance` (dropped temporal_memory)
- [x] API key pattern: `os.getenv("ANTHROPIC_API_KEY")` with explicit error (matches repo pattern)
- [x] Tests: 20 tests in `hackathon/tests/test_surveillance.py`

### Run command:
```bash
dimos --dtop --viewer rerun-web run unitree-go2-agentic-mcp-surveillance
```

## Phase 6: Room Intelligence — NOT STARTED (stretch)

- [ ] 2D room layout overlay on command center map
- [ ] Annotate desk assignments, room names, object locations
- [ ] Click room/desk → see who's there and what they're doing
