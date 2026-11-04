"""Busca nas políticas: trechos por seção, BM25 e embeddings.

O BM25 não tem dependência e é o padrão da ferramenta buscar_politica.
Os embeddings (fastembed) ficam no extra `rag` e entram na avaliação de busca.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import cache

from toolbr.paths import DATA_DIR

WORLD_NAMES = ("delivery", "banco", "atendimento")


def normalize(text: str) -> str:
    """Minúsculas e sem acento: 'Política' e 'politica' viram a mesma palavra."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


STOPWORDS = frozenset(
    normalize(w)
    for w in """a o as os um uma uns umas de do da dos das em no na nos nas por pelo pela
    pelos pelas para pra com sem sobre entre e ou que se não sim ao aos à às é ser ter tem
    eu você vocês ele ela eles elas meu minha meus minhas seu sua seus suas isso isto esse
    essa este esta qual quais como quando onde quanto quanta mais menos muito já só até
    depois antes há foi são está estão vai pode posso quero queria""".split()
)


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"\w+", normalize(text))
    return [_stem(t) for t in tokens if t not in STOPWORDS and len(t) > 1]


def _stem(token: str) -> str:
    """Radical simples de português: tira plural e algumas terminações comuns."""
    for suffix in ("coes", "cao", "mente", "idade", "oes", "aos", "ais", "eis", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


@dataclass(frozen=True)
class Chunk:
    id: str
    world: str
    title: str
    text: str


@cache
def load_chunks(world: str) -> tuple[Chunk, ...]:
    """Divide a política do mundo em trechos, um por seção '## '."""
    raw = (DATA_DIR / "mundos" / world / "politica.md").read_text(encoding="utf-8")
    chunks = []
    for block in re.split(r"^## ", raw, flags=re.M)[1:]:
        title, _, body = block.partition("\n")
        slug = re.sub(r"\W+", "_", normalize(title.strip())).strip("_")
        chunks.append(Chunk(f"{world}:{slug}", world, title.strip(), body.strip()))
    return tuple(chunks)


def all_chunks() -> tuple[Chunk, ...]:
    return tuple(c for w in WORLD_NAMES for c in load_chunks(w))


class BM25Retriever:
    """Okapi BM25 (k1=1.5, b=0.75) sobre título + texto de cada trecho."""

    name = "bm25"

    def __init__(self, chunks: tuple[Chunk, ...], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(f"{c.title} {c.text}")) for c in chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = sum(self.lengths) / max(len(self.lengths), 1)
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        terms = tokenize(query)
        scores = []
        for i, doc in enumerate(self.docs):
            score = 0.0
            for t in terms:
                tf = doc.get(t, 0)
                if tf:
                    norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg_len)
                    score += self.idf[t] * tf * (self.k1 + 1) / (tf + norm)
            scores.append((self.chunks[i], score))
        scores.sort(key=lambda pair: pair[1], reverse=True)
        return scores[:k]


class EmbeddingRetriever:
    """Similaridade de cosseno entre embeddings da pergunta e dos trechos.

    `model` aceita 'fastembed:<nome>' (local, grátis) ou 'openai:<nome>' (pago).
    """

    def __init__(self, chunks: tuple[Chunk, ...], model: str):
        self.chunks = chunks
        self.name = f"embeddings ({model})"
        backend, _, model_name = model.partition(":")
        if backend == "fastembed":
            from fastembed import TextEmbedding

            encoder = TextEmbedding(model_name=model_name)
            self._embed = lambda texts: [list(v) for v in encoder.embed(texts)]
        elif backend == "openai":
            from openai import OpenAI

            client = OpenAI()
            self._embed = lambda texts: [
                d.embedding for d in client.embeddings.create(model=model_name, input=texts).data
            ]
        else:
            raise ValueError(f"backend de embedding desconhecido: {backend!r}")
        self.vectors = [_unit(v) for v in self._embed([f"{c.title}. {c.text}" for c in chunks])]

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        q = _unit(self._embed([query])[0])
        scores = [
            (c, sum(a * b for a, b in zip(q, v, strict=True)))
            for c, v in zip(self.chunks, self.vectors, strict=True)
        ]
        scores.sort(key=lambda pair: pair[1], reverse=True)
        return scores[:k]


def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]
