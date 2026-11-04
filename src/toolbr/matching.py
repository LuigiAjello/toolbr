"""Casamento de texto da resposta: sempre por palavra inteira, nunca por substring.

Armadilha que já aconteceu: casar "id" por substring fez "resolvido" passar.
Aqui "id" só casa com a palavra "id" isolada.
"""

from __future__ import annotations

import re
from typing import Any

from toolbr.retrieval import normalize


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", normalize(text)).strip()


def contains_phrase(text: str, phrase: str) -> bool:
    """`phrase` aparece em `text` como palavra(s) inteira(s), ignorando acento e maiúscula."""
    pattern = r"(?<!\w)" + re.escape(_clean(phrase)) + r"(?!\w)"
    return re.search(pattern, _clean(text)) is not None


def money_variants(value: float) -> list[str]:
    """Formas comuns de escrever um valor: 1.250,00 / 1250,00 / 1250.00 / 1.250 / 1250."""
    cents = round(value * 100)
    integer, frac = divmod(abs(cents), 100)
    br_thousands = f"{integer:,}".replace(",", ".")
    variants = {
        f"{br_thousands},{frac:02d}",
        f"{integer},{frac:02d}",
        f"{integer}.{frac:02d}",
    }
    if frac == 0:
        variants |= {br_thousands, str(integer)}
    elif frac % 10 == 0:
        variants |= {f"{br_thousands},{frac // 10}", f"{integer},{frac // 10}"}
    return sorted(variants)


def item_matches(text: str, item: Any) -> bool:
    """Um item de resposta_deve_conter: texto, {valor: x} ou lista de alternativas."""
    if isinstance(item, list):
        return any(item_matches(text, alt) for alt in item)
    if isinstance(item, dict):
        return any(contains_phrase(text, v) for v in money_variants(float(item["valor"])))
    return contains_phrase(text, str(item))


def check_response(text: str, must: list[Any], must_not: list[Any] | None = None) -> bool:
    text = text or ""
    if not all(item_matches(text, item) for item in must):
        return False
    return not any(item_matches(text, item) for item in must_not or [])
