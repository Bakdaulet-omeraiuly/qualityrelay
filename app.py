"""Vercel entry point (FastAPI zero-config, root app.py): the QualityRelay Studio (FastAPI) as one Python serverless function.
Read-only filesystem: photo capture / reference saving and OpenCV photo measurement are not
available on this deployment (run locally for those). Everything shown is SIMULATED."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from qualityrelay17.api import app  # noqa: E402,F401
