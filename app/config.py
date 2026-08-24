from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "regex_intelligence.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
ANALYSIS_VERSION = "1.0.0"
REGEX_VERSION = "1.0.0"
NEGATION_WINDOW = 48
LANGUAGE_TIC_DENSITY_LIMIT = 0.02
MAX_UPLOAD_FILES = 500
MAX_FILE_BYTES = 50_000_000
