"""Promo Finder: reads timestamped microdrama screenplays and returns ranked 20-60 s promo cuts."""
from .parser import load_path, load_zip_bytes, parse_text  # noqa: F401
from .pipeline import run  # noqa: F401

__version__ = "1.0.0"
