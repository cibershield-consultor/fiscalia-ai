"""Tests for RAG knowledge base search."""
import pytest
from app.services.rag_service import search_knowledge_base, _tokenize, _score_document


def test_tokenizer_normalizes_accents():
    tokens = _tokenize("IVA autónomo")
    assert "iva" in tokens
    assert "autonomo" in tokens

def test_search_iva_query():
    results = search_knowledge_base("¿Cuál es el tipo de IVA general?", n_results=3)
    assert len(results) >= 1
    # IVA document should be most relevant
    assert any("iva" in r["id"].lower() for r in results)

def test_search_autonomos_query():
    results = search_knowledge_base("cuota de autónomo por ingresos reales", n_results=3)
    assert any("autono" in r["id"].lower() for r in results)

def test_search_irpf_query():
    results = search_knowledge_base("tramos IRPF 2026 retención", n_results=3)
    assert any("irpf" in r["id"].lower() for r in results)

def test_search_lgss_query():
    results = search_knowledge_base("cese de actividad autónomo RETA prestación", n_results=3)
    ids = [r["id"] for r in results]
    assert any("lgss" in i or "autonomo" in i for i in ids)

def test_search_returns_sources_with_urls():
    results = search_knowledge_base("IVA factura", n_results=2)
    for r in results:
        assert "source" in r
        assert "url" in r

def test_search_empty_query_returns_results():
    results = search_knowledge_base("", n_results=3)
    assert len(results) >= 1

def test_score_document_relevance():
    doc = {"text": "IVA España 21% tipo general", "keywords": ["iva", "21%"]}
    score_relevant = _score_document(["iva", "tipo"], doc)
    score_irrelevant = _score_document(["jubilacion", "pension"], doc)
    assert score_relevant > score_irrelevant
