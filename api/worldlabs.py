"""Vercel serverless proxy to World Labs API.

Forwards requests to World Labs API, injecting the API key from env.
Client calls: /api/worldlabs?path=<world-labs-endpoint>
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs

WL_BASE = "https://api.worldlabs.ai/marble/v1"


class handler(BaseHTTPRequestHandler):
    def _get_api_key(self):
        return os.environ.get("WLT_API_KEY", "")

    def _get_wl_path(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        return params.get("path", [""])[0]

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _proxy(self, method):
        api_key = self._get_api_key()
        wl_path = self._get_wl_path()

        if not wl_path:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing path parameter"}).encode())
            return

        url = f"{WL_BASE}/{wl_path}"
        headers = {"WLT-Api-Key": api_key}

        body = None
        if method == "POST":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body = self.rfile.read(content_length)
                headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self):
        self._proxy("GET")

    def do_POST(self):
        self._proxy("POST")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()
