"""
Compatibility wrapper so legacy imports (`from google_functions import ...`)
continue to work after moving the implementation under `backend/`.
"""
from backend.google_functions import *  # noqa: F401,F403
