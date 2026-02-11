"""Schedule integrity module for tamper detection and delayed changes.

Detects external edits to settings.json schedules and enforces a 24-hour
delay before changes take effect. This creates friction against impulsive
schedule modifications while still allowing legitimate changes.
"""

import hashlib
import json
import os
from datetime import datetime, timedelta

PENDING_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".pending_schedule.json",
)

DELAY_HOURS = 24


def compute_schedule_hash(schedule: dict) -> str:
    """Compute a deterministic SHA-256 hash of a schedule dictionary.

    Args:
        schedule: The schedule dictionary to hash.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    canonical = json.dumps(schedule, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_pending_schedule(new_schedule: dict, old_schedule: dict) -> str:
    """Save a pending schedule change that will apply after the delay.

    If a pending file already exists with a different schedule, it is
    replaced and the timer resets. If the pending schedule matches the
    one already waiting, the existing timer is preserved.

    Args:
        new_schedule: The newly detected schedule from settings.json.
        old_schedule: The current active schedule to preserve as fallback.

    Returns:
        ISO-8601 timestamp when the pending schedule will apply.
    """
    # Check if there's already a pending file with the same schedule
    existing = load_pending_schedule()
    if existing is not None:
        existing_hash = compute_schedule_hash(existing["schedule"])
        new_hash = compute_schedule_hash(new_schedule)
        if existing_hash == new_hash:
            # Same change already pending — keep existing timer
            return existing["applies_at"]

    applies_at = (datetime.now() + timedelta(hours=DELAY_HOURS)).isoformat()
    pending_data = {
        "schedule": new_schedule,
        "old_schedule": old_schedule,
        "applies_at": applies_at,
    }
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending_data, f, indent=4)
    return applies_at


def load_pending_schedule() -> dict | None:
    """Load the pending schedule file if it exists.

    Returns:
        The pending schedule data dict, or None if no pending file exists.
    """
    if not os.path.exists(PENDING_FILE):
        return None
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def check_and_promote_pending() -> dict | None:
    """Check if a pending schedule is ready to be promoted.

    If the pending schedule's delay has elapsed, returns the new schedule
    and removes the pending file. Otherwise returns None.

    Returns:
        The new schedule dict if promotion happened, None otherwise.
    """
    pending = load_pending_schedule()
    if pending is None:
        return None

    applies_at = datetime.fromisoformat(pending["applies_at"])
    if datetime.now() >= applies_at:
        # Time's up — promote the pending schedule
        clear_pending()
        return pending["schedule"]
    return None


def clear_pending():
    """Remove the pending schedule file."""
    if os.path.exists(PENDING_FILE):
        os.remove(PENDING_FILE)


def get_pending_time_remaining() -> str | None:
    """Get a human-readable string of time remaining for a pending change.

    Returns:
        String like '23h 15m' or None if no pending schedule exists.
    """
    pending = load_pending_schedule()
    if pending is None:
        return None

    applies_at = datetime.fromisoformat(pending["applies_at"])
    remaining = applies_at - datetime.now()

    if remaining.total_seconds() <= 0:
        return "applying soon"

    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
