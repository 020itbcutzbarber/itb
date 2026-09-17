import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("ITBCUTZ_DB_PATH", "/tmp/itbcutz.sqlite3")
os.environ.setdefault("ITBCUTZ_UPLOAD_DIR", "/tmp/itbcutz_uploads")

from server import App, init_db

init_db()


class handler(App):
    pass
