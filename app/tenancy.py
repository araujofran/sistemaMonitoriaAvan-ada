from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
import re
import unicodedata

from .config import DATA_DIR, DATABASE_PATH

PRODUCT_DB_DIR = DATA_DIR / "products"
ACTIVE_DATABASE: ContextVar[Path | None] = ContextVar("active_database", default=None)


def slugify(value: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFD", value.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def product_database(slug: str) -> Path:
    safe = slugify(slug)
    if not safe: raise ValueError("Produto inválido")
    PRODUCT_DB_DIR.mkdir(parents=True, exist_ok=True)
    return PRODUCT_DB_DIR / f"{safe}.db"


def active_database() -> Path | None:
    return ACTIVE_DATABASE.get()
