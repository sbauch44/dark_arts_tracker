"""Scoring models.

* :mod:`heuristic` — v1, hand-weighted on §2 patterns.
* :mod:`logistic` — v2, regularized logistic regression learned from the
  labeled set.
* :mod:`bayesian` — v3, hierarchical pymc model with partial pooling
  across sector and governance-tier and a joint MNPI-label + forward-return
  likelihood.
"""
