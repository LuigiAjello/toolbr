"""Todo arquivo citado no README precisa existir (no CI, só existe o que foi commitado)."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_every_local_link_in_readme_exists():
    readme = (ROOT / "README.md").read_text("utf-8")
    links = set(re.findall(r"\]\(((?!https?://|#)[^)\s]+)\)", readme))
    links |= set(re.findall(r'src="((?!https?://)[^"]+)"', readme))
    missing = sorted(link for link in links if not (ROOT / link).exists())
    assert not missing, f"o README cita arquivos que não existem: {missing}"
    assert any(link.startswith("results/") for link in links)
