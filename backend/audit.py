import json
import time
from pathlib import Path

LOG_FILE = Path(__file__).parent / "audit_log.json"
_log: list[dict] = []


def record(session_id: str, action: str, details: dict, status: str = "success", error: str = None):
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": session_id,
        "action": action,
        "status": status,
        "details": details,
    }
    if error:
        entry["error"] = error
    _log.append(entry)
    _persist()
    return entry


def get_session_log(session_id: str) -> list[dict]:
    return [e for e in _log if e["session_id"] == session_id]


def get_all() -> list[dict]:
    return _log


def _persist():
    try:
        LOG_FILE.write_text(json.dumps(_log, indent=2))
    except Exception:
        pass
