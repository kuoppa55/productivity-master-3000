from mitmproxy import http
import json
import os

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_state.json")
BLOCK_PAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "block_page.html")

FOCUS_ONLY_BLOCKS = [
    "youtube.com",
    "reddit.com",
    "boards.4chan.org",
    "kiwifarms.st",
    "x.com",
    "twitter.com",
]

PERMANENT_BLOCKS = [
    "skipthegames.com",
    "megapersonals.eu",
    "longisland.bedpage.com",
    "boards.4chan.org/gif/",
    "boards.4chan.org/soc/"
]

try:
    if os.path.exists(BLOCK_PAGE_FILE):
        with open(BLOCK_PAGE_FILE, "r", encoding="utf-8") as f:
            BLOCK_HTML = f.read().encode("utf-8")
    else:
        # Fallback if file is missing
        BLOCK_HTML = b"<h1>Blocked</h1><p>block_page.html missing.</p>"
except Exception as e:
    BLOCK_HTML = f"<h1>Error</h1><p>{e}</p>".encode("utf-8")

def get_focus_state():
    if not os.path.exists(STATE_FILE):
        return False
    
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return data.get("focus_active", False)
    except:
        return False

def request(flow: http.HTTPFlow) -> None:
    url_path = flow.request.pretty_url
    host = flow.request.pretty_host

    if "googlevideo.com" in host:
        return
    
    if any(filter_txt in url_path for filter_txt in PERMANENT_BLOCKS):
        block_request(flow)
        return
    
    is_focus_active = get_focus_state()
    if not is_focus_active:
        return

    if any(domain in host for domain in FOCUS_ONLY_BLOCKS):
        if "youtube.com" in host:
            if "watch?v=" in url_path:
                return # Allow video playback
            elif "studio.youtube.com" in host or "/upload" in url_path:
                return # Allow creators
            elif "/s/player" in url_path or "/youtubei/" in url_path or "/api/" in url_path:
                return # Allow backend API
            else:
                pass # Block main page/feed
                
        block_request(flow)

def block_request(flow: http.HTTPFlow):
    """Helper function to send the block response"""
    flow.response = http.Response.make(
        403,  # Status code
        BLOCK_HTML, # Response body
        {
            "Content-Type": "text/html",
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Clear-Site-Data": '"cache", "storage"'
        }
    )