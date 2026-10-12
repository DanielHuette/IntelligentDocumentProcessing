"""Tests for the synthetic corpus."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from idp.corpus import generate_corpus, load_corpus, write_corpus
from idp.domain import Defect, DocumentFormat, DocumentType, LabeledDocument, Route
from idp.vendors import german_iban


def test_corpus_is_reproducible() -> None:
    first, second = generate_corpus(60, 7), generate_corpus(60, 7)
    assert [d.text for d in first] == [d.text for d in second]


def test_corpus_rejects_tiny_sizes() -> None:
    with pytest.raises(ValueError, match="at least 50"):
        generate_corpus(10)


def test_corpus_covers_every_type_format_and_defect(corpus: list[LabeledDocument]) -> None:
    assert len(corpus) == 250
    assert len({d.doc_id for d in corpus}) == 250
    assert {d.truth.document_type for d in corpus} == set(DocumentType)
    assert {d.document_format for d in corpus} == set(DocumentFormat)
    defects = Counter(d for doc in corpus for d in doc.truth.defects)
    assert set(defects) == set(Defect)


def test_only_clean_known_invoices_are_approved(corpus: list[LabeledDocument]) -> None:
    for document in corpus:
        truth = document.truth
        expected = truth.document_type == DocumentType.INVOICE and not truth.defects
        assert (truth.route == Route.APPROVED) == expected


def test_clean_invoice_totals_add_up(corpus: list[LabeledDocument]) -> None:
    for document in corpus:
        truth = document.truth
        if truth.route == Route.APPROVED and truth.amounts is not None:
            a = truth.amounts
            assert a.net + a.tax == a.gross


def test_duplicates_follow_their_originals(corpus: list[LabeledDocument]) -> None:
    positions = {d.text: i for i, d in reversed(list(enumerate(corpus)))}
    for index, document in enumerate(corpus):
        if Defect.DUPLICATE in document.truth.defects:
            assert positions[document.text] < index


def test_corpus_round_trip(tmp_path: Path) -> None:
    documents = generate_corpus(60, 3)
    path = tmp_path / "corpus.jsonl"
    write_corpus(documents, path)
    assert list(load_corpus(path)) == documents


def test_german_iban_has_valid_check_digits() -> None:
    iban = german_iban("37010050", "248586505").replace(" ", "")
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(c, 36)) for c in rearranged)
    assert int(digits) % 97 == 1


@pytest.mark.parametrize(("bank", "account"), [("123", "1"), ("12345678", "12345678901")])
def test_german_iban_rejects_bad_input(bank: str, account: str) -> None:
    with pytest.raises(ValueError, match="must have"):
        german_iban(bank, account)
