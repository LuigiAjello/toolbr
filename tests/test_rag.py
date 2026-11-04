from toolbr.rag_eval import compare_methods, evaluate, load_questions
from toolbr.retrieval import BM25Retriever, all_chunks, load_chunks, tokenize


def test_questions_point_to_existing_chunks():
    ids = {c.id for c in all_chunks()}
    questions = load_questions()
    assert len(questions) == 15
    assert all(q["trecho"] in ids for q in questions)


def test_tokenizer_ignores_accents_case_and_stopwords():
    assert tokenize("A Política de REEMBOLSO") == tokenize("politica reembolso")


def test_bm25_ranks_lexical_match_first():
    r = BM25Retriever(load_chunks("delivery"))
    assert (
        r.search("quanto tempo conta como atraso grande", k=1)[0][0].id == "delivery:atraso_grande"
    )


class PerfectRetriever:
    name = "perfeito"

    def __init__(self, chunks, gold):
        self.chunks, self.gold = chunks, gold

    def search(self, query, k=3):
        first = next(c for c in self.chunks if c.id == self.gold[query])
        rest = [c for c in self.chunks if c.id != first.id]
        return [(c, 1.0) for c in [first, *rest]][:k]


def test_metrics_with_perfect_and_bm25_retrievers():
    questions = load_questions()
    gold = {q["pergunta"]: q["trecho"] for q in questions}
    perfect = evaluate(PerfectRetriever(all_chunks(), gold), questions)
    assert perfect["recall@1"] == perfect["mrr"] == 1.0 and not perfect["erros_no_top1"]
    bm25 = evaluate(BM25Retriever(all_chunks()), questions)
    assert bm25["recall@1"] <= bm25["recall@3"] <= bm25["recall@5"] <= 1.0
    assert bm25["mrr_ic95"][0] <= bm25["mrr"] <= bm25["mrr_ic95"][1]
    diff = compare_methods(bm25, perfect)
    assert diff["diferenca"] > 0
