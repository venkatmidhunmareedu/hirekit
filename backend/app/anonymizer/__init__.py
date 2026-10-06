"""The anonymizer: the only producer of `AnonymizedText` (tenet 2).

A floor, not proof of fairness: it removes named signals only.
"""

from app.anonymizer.loader import load_anonymized
from app.anonymizer.pipeline import Anonymized, anonymize

__all__ = ["Anonymized", "anonymize", "load_anonymized"]
