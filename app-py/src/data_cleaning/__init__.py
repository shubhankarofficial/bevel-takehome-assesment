"""
Data cleaning checks for USDA CSV inputs.

This package runs validation and cleaning checks on the CSVs before or during ingest.
Even when no cleaning is required, the code documents what we looked for and reports
that nothing needed cleaning—so the intent is visible and extensible for future rules.
"""

from .report import CleaningReport, run_cleaning_checks

__all__ = ["CleaningReport", "run_cleaning_checks"]
