import pathlib
import sys

# The server runs as flat top-level modules (see Dockerfile: uvicorn app:app); make them importable in tests.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
