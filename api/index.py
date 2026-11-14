import os
import sys
import urllib.parse

# Ensure root directory is in sys.path for local module resolution
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import TavolaraHandler

class handler(TavolaraHandler):
    """
    Vercel Serverless Function entrypoint for Tavolara Wear.
    Handles all /api/* routes seamlessly by extracting the real requested path.
    """
    def _normalize_path(self):
        # On Vercel, destination /api/index.py replaces self.path.
        # The true requested path is available in x-vercel-original-uri or x-forwarded-uri.
        orig = (
            self.headers.get("x-vercel-original-uri")
            or self.headers.get("x-forwarded-uri")
            or self.headers.get("x-matched-path")
        )
        if orig:
            self.path = orig

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
