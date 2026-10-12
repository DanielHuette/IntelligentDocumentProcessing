"""Synthetic accounts-payable inbox with known answers.

Context: Produces the benchmark corpus. | Input: Size and seed. | Output: Labeled documents.
"""

from idp.corpus.generate import generate_corpus, load_corpus, write_corpus

__all__ = ["generate_corpus", "load_corpus", "write_corpus"]
