import json, os
import urllib.request
from mitmproxy import http

DASHBOARD = os.environ.get("DASHBOARD_URL", "http://172.20.0.50:3000")

def _post(payload: dict):
    try:
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            f"{DASHBOARD}/mitm-event", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass

class LabAddon:
    def request(self, flow: http.HTTPFlow) -> None:
        _post({"event": "request", "method": flow.request.method,
               "url": flow.request.pretty_url,
               "headers": dict(flow.request.headers),
               "body": flow.request.content.decode("utf-8", errors="replace")})

    def response(self, flow: http.HTTPFlow) -> None:
        _post({"event": "response", "status": flow.response.status_code,
               "url": flow.request.pretty_url,
               "headers": dict(flow.response.headers),
               "body": flow.response.content.decode("utf-8", errors="replace")})

addons = [LabAddon()]
