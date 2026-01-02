from mitmproxy import http

TARGET_DOMAINS = [
    "youtube.com", 
    "reddit.com", 
    "kiwifarms.st", 
    "skipthegames.com", 
    "megapersonals.eu", 
    "longisland.bedpage.com", 
    "boards.4chan.org"
]

def request(flow: http.HTTPFlow) -> None:
    url_path = flow.request.pretty_url
    host = flow.request.pretty_host

    if "googlevideo.com" in host:
        return

    is_target_domain = any(domain in host for domain in TARGET_DOMAINS)
    if not is_target_domain:
        return
    
    if "youtube.com" in host:
        if "watch?v=" in url_path:
            return
        
        if "studio.youtube.com" in host or "/upload" in url_path:
            return
        
        if "/s/player" in url_path:
            return
        
        if "/youtubei/" in url_path or "/api/" in url_path:
            return 
        
        flow.response = http.Response.make(
            403,  # Status code
            b"Blocked by Productivity Master 3000",  # Response body
            {
                "Content-Type": "text/html",
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Clear-Site-Data": '"cache", "storage"'
            } 
        )
        return
    flow.response = http.Response.make(
        403,  # Status code
        b"Blocked by Productivity Master 3000",  # Response body
        {
            "Content-Type": "text/html",
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Clear-Site-Data": '"cache", "storage"'
        }
    )