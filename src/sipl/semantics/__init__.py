"""Формальна семантика SIPL: семантичні терми (SEM-01)."""
from .builder import Construction, RuleStep, build_term, semantic_term
from .terms import STYLES, Term, format_term, term_to_dict

__all__ = ["Construction", "RuleStep", "STYLES", "Term", "build_term", "format_term",
           "semantic_term", "term_to_dict"]
