import os
import sys

# Ensure root directory is in sys.path for local module resolution
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import TavolaraHandler

class handler(TavolaraHandler):
    """
    Vercel Serverless Function entrypoint for Tavolara Wear.
    Handles all /api/* routes seamlessly.
    """
    def log_message(self, format, *args):
        # Format serverless logs cleanly
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))
