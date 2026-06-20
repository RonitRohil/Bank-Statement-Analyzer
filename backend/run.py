import os
import warnings
from app import create_app

warnings.warn(
    "Flask backend (port 5000) is deprecated as of Sprint-02. "
    "Use FastAPI backend (port 8000) via backend-v2/run.py. "
    "Flask will be removed in Sprint-03.",
    DeprecationWarning,
    stacklevel=2,
)

app = create_app()

if __name__ == '__main__':
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(port=5000, debug=debug)
