"""
Full analysis pipeline for conversation transcripts.

Orchestrates metrics calculation, failure detection, and auto-improvement
suggestions into a unified analysis report.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from src.schemas.conversation_schema import ConversationTranscript
from src.evaluation.metrics import MetricsCalculator, EvalMetrics
from src.evaluation.failure_detector import FailureDetector, DetectedFailure
from src.evaluation.auto_improver import AutoImprover, PromptSuggestion

logger = logging.getLogger(__name__)


@dataclass
class TranscriptAnalysis:
    """Complete analysis of a single transcript."""
    call_id: str
    metrics: EvalMetrics
    failures: list[DetectedFailure]
    suggestions: list[PromptSuggestion]


@dataclass
class BatchReport:
    """Aggregated report across multiple transcripts."""
    total_calls: int
    analyses: list[TranscriptAnalysis]
    aggregate_metrics: EvalMetrics
    all_failures: list[DetectedFailure]
    all_suggestions: list[PromptSuggestion]
    failure_summary: dict[str, int] = field(default_factory=dict)


class TranscriptAnalyzer:
    """Orchestrates the full evaluation pipeline."""

    def __init__(self) -> None:
        self._metrics = MetricsCalculator()
        self._failures = FailureDetector()
        self._improver = AutoImprover()

    def analyze(self, transcript: ConversationTranscript) -> TranscriptAnalysis:
        """Run full analysis on a single transcript."""
        metrics = self._metrics.calculate(transcript)
        failures = self._failures.detect_all(transcript)
        suggestions = self._improver.suggest_improvements(failures)

        return TranscriptAnalysis(
            call_id=transcript.call_id,
            metrics=metrics,
            failures=failures,
            suggestions=suggestions,
        )

    def analyze_batch(self, transcripts: list[ConversationTranscript]) -> BatchReport:
        """Run analysis on a batch of transcripts and aggregate results."""
        analyses = [self.analyze(t) for t in transcripts]

        all_failures = []
        for a in analyses:
            all_failures.extend(a.failures)

        all_suggestions = self._improver.suggest_improvements(all_failures)
        aggregate_metrics = self._metrics.calculate_batch(transcripts)

        failure_summary: dict[str, int] = {}
        for f in all_failures:
            failure_summary[f.pattern.value] = failure_summary.get(f.pattern.value, 0) + 1

        return BatchReport(
            total_calls=len(transcripts),
            analyses=analyses,
            aggregate_metrics=aggregate_metrics,
            all_failures=all_failures,
            all_suggestions=all_suggestions,
            failure_summary=failure_summary,
        )

    def load_transcript(self, path: Path) -> ConversationTranscript:
        """Load a transcript from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ConversationTranscript(**data)

    def load_directory(
        self, directory: Path, *, strict: bool = False
    ) -> list[ConversationTranscript]:
        """Load all transcript JSON files from a directory.

        Args:
            directory: Path to the directory containing JSON transcript files.
            strict: If True, raise on the first load failure instead of skipping.
        """
        transcripts: list[ConversationTranscript] = []
        failed: list[tuple[str, str]] = []

        for path in sorted(directory.glob("*.json")):
            try:
                transcripts.append(self.load_transcript(path))
                logger.debug("Loaded transcript: %s", path.name)
            except Exception as e:
                if strict:
                    raise
                failed.append((path.name, str(e)))
                logger.warning("Failed to load %s: %s", path.name, e)

        if failed:
            logger.warning(
                "Skipped %d of %d transcript files: %s",
                len(failed),
                len(failed) + len(transcripts),
                ", ".join(name for name, _ in failed),
            )

        return transcripts

    def format_batch_report(self, report: BatchReport) -> str:
        """Format a batch report into a human-readable string."""
        lines = [
            self._metrics.format_report(report.aggregate_metrics),
            "",
            f"ANALYZED: {report.total_calls} conversations",
            "",
        ]

        if report.failure_summary:
            lines.append("FAILURE PATTERN SUMMARY:")
            for pattern, count in sorted(
                report.failure_summary.items(), key=lambda x: -x[1]
            ):
                lines.append(f"  {pattern}: {count} occurrence(s)")
            lines.append("")

        if report.all_suggestions:
            lines.append(self._improver.format_suggestions(report.all_suggestions))

        # Per-call summary
        lines.append("")
        lines.append("PER-CALL BREAKDOWN:")
        for analysis in report.analyses:
            status = "PASS" if analysis.metrics.success_rate > 0 else "FAIL"
            failure_count = len(analysis.failures)
            lines.append(
                f"  [{status}] {analysis.call_id} — "
                f"{failure_count} failure(s), "
                f"fill rate: {analysis.metrics.slot_fill_rate:.0%}"
            )

        return "\n".join(lines)
