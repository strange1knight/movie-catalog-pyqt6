"""Application paths that also work in a packaged executable."""

import os
import sys
from pathlib import Path

from PyQt6.QtCore import QStandardPaths


def resource_path(name):
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "movie_catalog"
    else:
        base = Path(__file__).resolve().parent
    return base / name


def data_dir():
    override = os.environ.get("MOVIE_CATALOG_DATA_DIR")
    if override:
        root = Path(override)
    else:
        root = Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        ))
    root.mkdir(parents=True, exist_ok=True)
    return root
