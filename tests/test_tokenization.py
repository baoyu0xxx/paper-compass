"""Tests for sparse-search tokenization."""

from paper_compass.tokenization import tokenize_for_sparse_search


def test_tokenize_for_sparse_search_emits_cjk_bigrams():
    tokens = tokenize_for_sparse_search("代际传承")

    assert tokens == ["代际", "际传", "传承"]
    assert all(tokens)


def test_tokenize_for_sparse_search_keeps_mixed_ascii_tokens():
    tokens = tokenize_for_sparse_search("CEO 继任 DID treat_post Tobin Q")

    assert "ceo" in tokens
    assert "did" in tokens
    assert "treat_post" in tokens
    assert "tobin" in tokens
    assert "q" in tokens
    assert "继任" in tokens
    assert all(tokens)
