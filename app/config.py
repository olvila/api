import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

NIM_API_KEY = os.getenv("NIM_API_KEY", "")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "30"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
REQUEST_TIMEOUT_SEC = int(os.getenv("REQUEST_TIMEOUT_SEC", "60"))

_MOI_KEYS_RAW = os.getenv("MOI_KEYS", "")
VALID_MOI_KEYS = {k.strip() for k in _MOI_KEYS_RAW.split(",") if k.strip()}
