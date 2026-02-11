# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Productivity Master 3000 is a Windows desktop application that enforces focused work sessions by blocking distracting websites via a local HTTPS proxy. It has three integrated layers:

1. **GUI (main.pyw)** — CustomTkinter app with focus toggle, schedule management, system tray, and Windows startup integration
2. **Proxy Service (focus_logic_simple.py)** — mitmproxy-based HTTP/HTTPS interceptor that blocks domains based on focus state and block lists
3. **Background Scheduler** — APScheduler job that auto-enables focus mode during configured time blocks

## Running the Application

```bash
# Activate virtual environment
venv\Scripts\activate

# Run the app
python productivity_master_3000/main.pyw
# Or use the batch launcher:
productivity_master_3000\ProductivityManager3000.bat
```

The GUI automatically starts the proxy service (`mitmdump -s focus_logic_simple.py` on 127.0.0.1:8080) and configures the Windows system proxy via registry.

## Dependencies

Install with: `pip install mitmproxy customtkinter apscheduler pystray pillow pydivert`

No requirements.txt exists — dependencies are installed directly.

## Testing

No automated test suite exists. Testing is manual: launch the app, enable focus mode, verify blocked sites show the block page, test cooldown timer, and test schedule enforcement.

## Architecture Details

### State Communication
The GUI and proxy service communicate through **app_state.json** (`{"focus_active": true/false}`). The GUI writes this file on toggle; the proxy reads it on every request to decide whether to block.

### Block List System (blocklist.json)
Two categories of blocks:
- **focus_only_blocks**: Domains blocked only when focus mode is active (e.g., youtube.com, reddit.com, x.com)
- **permanent_blocks**: Domains/paths blocked regardless of focus state

YouTube has special handling during focus: video playback (`watch?v=`), creator tools (`studio.youtube.com`), and the player API (`/youtubei/v1/player`, `/s/player`) are allowed. All browsing/discovery endpoints (`/youtubei/v1/browse`, `/search`, `/guide`, `/next`) are blocked to prevent SPA navigation in cached tabs.

### Domain Matching
Uses suffix matching: `host == domain or host.endswith('.' + domain)`. Supports both domain-level blocking and URL path-level blocking for granular control.

### Cooldown Mechanism
When focus mode is deactivated (by user or schedule end), a mandatory 90-second cooldown period prevents immediate re-toggling. The app also prevents quitting during cooldown unless triggered by the scheduler.

### Windows Integration
- **System proxy**: Set/unset via `HKEY_CURRENT_USER\...\Internet Settings` registry keys, refreshed with `wininet.dll` calls
- **Startup**: Registered in `HKEY_CURRENT_USER\...\Run` registry key

### Schedule Tamper Protection (schedule_integrity.py)
Edits to the schedule in `settings.json` are detected via SHA-256 hash comparison. External changes are not applied immediately — they go into a 24-hour pending queue (`.pending_schedule.json`). The old schedule is preserved in `.schedule_backup.json` and restored until the delay expires. The `_enforce_schedule_logic()` method checks for pending promotions every minute.

### Key Files
| File | Purpose |
|------|---------|
| `main.pyw` | GUI app entry point, all UI and control logic |
| `focus_logic_simple.py` | mitmproxy addon that filters requests |
| `schedule_integrity.py` | Schedule hash verification and 24h pending delay |
| `blocklist.json` | External block list configuration |
| `settings.json` | User preferences, weekly schedule, and schedule hash |
| `app_state.json` | Runtime focus state (shared between GUI and proxy) |
| `.pending_schedule.json` | Transient file for delayed schedule changes |
| `.schedule_backup.json` | Backup of last known good schedule |
| `block_page.html` | HTML served when a site is blocked (403 response) |
| `make_icon.py` | Utility to generate .ico from PNG artwork |

### Key Classes
- **`ProductivityMaster3000App(ctk.CTk)`** in `main.pyw` — Main application window with all UI and lifecycle logic
- **`SettingManager`** in `main.pyw` — Static class for loading/saving settings.json with schedule tamper detection
