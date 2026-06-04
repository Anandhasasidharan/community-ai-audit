"""
Reporting module. Converts scan and interpret results into
human-readable formats (Markdown, JSON, HTML, etc.).
"""

from .generator import ReportGenerator

__all__ = ["ReportGenerator"]
