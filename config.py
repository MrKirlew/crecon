"""
Compatibility wrapper so modules can `import config` while the canonical
implementation lives in `backend/config.py`.
"""
from backend.config import *  # noqa: F401,F403
