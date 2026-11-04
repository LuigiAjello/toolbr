"""Caminhos do projeto. TOOLBR_DATA permite apontar para outra pasta de dados."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("TOOLBR_DATA", ROOT / "data"))
RESULTS_DIR = Path(os.environ.get("TOOLBR_RESULTS", ROOT / "results"))
