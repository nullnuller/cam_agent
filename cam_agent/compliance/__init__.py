"""
Compliance rule definitions and evaluators.

Modules under this package will score LLM outputs against regulatory
requirements and produce allow/warn/block decisions.
"""

from .rules import ComplianceRule, DISCLAIMER_HINT, RULES, evaluate_compliance

__all__ = ["ComplianceRule", "RULES", "evaluate_compliance", "DISCLAIMER_HINT"]
