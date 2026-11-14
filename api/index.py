import os
import sys
import json
import urllib.parse

# Ensure root directory is in sys.path for local module resolution
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import TavolaraHandler, send_json

class handler(TavolaraHandler):
    """
    Vercel Serverless Function entrypoint for Tavolara Wear.
    """
    def _normalize_path(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        # Route via query param __path__ if passed by vercel.json
        if "__path__" in qs and qs["__path__"]:
            sub = qs["__path__"][0].lstrip("/")
            clean_qs = {k: v for k, v in qs.items() if k != "__path__"}
            new_query = urllib.parse.urlencode(clean_qs, doseq=True)
            new_path = "/api/" + sub
            self.path = f"{new_path}?{new_query}" if new_query else new_path
            return

        # Fallback to headers
        for h in ["x-vercel-original-uri", "x-forwarded-uri", "x-matched-path"]:
            val = self.headers.get(h)
            if val and val.startswith("/api"):
                self.path = val
                return

    def do_GET(self):
        self._normalize_path()
        super().do_GET()

    def do_POST(self):
        self._normalize_path()
        super().do_POST()

    def do_PUT(self):
        self._normalize_path()
        super().do_PUT()

    def do_PATCH(self):
        self._normalize_path()
        super().do_PATCH()

    def do_DELETE(self):
        self._normalize_path()
        super().do_DELETE()

    def do_OPTIONS(self):
        self._normalize_path()
        super().do_OPTIONS()

    def log_message(self, format, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))
