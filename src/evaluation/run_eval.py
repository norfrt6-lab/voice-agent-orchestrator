"""
CLI entry point for running evaluation on transcript files.

Usage:
    python -m src.evaluation.run_eval --transcripts sample_transcripts/ --verbose
    python -m src.evaluation.run_eval --transcripts sample_transcripts/ --report report.txt
"""

import argparse
import logging
import sys
from pathlib import Path

from src.evaluation.transcript_analyzer import TranscriptAnalyzer

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate voice agent conversations from transcript files."
    )
    parser.add_argument(
        "--transcripts",
        type=str,
        required=True,
        help="Path to directory containing transcript JSON files.",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Path to write the evaluation report (default: stdout).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output.",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s: %(message)s",
        )

    transcript_dir = Path(args.transcripts)
    if not transcript_dir.exists():
        logger.error("Transcript directory not found: %s", transcript_dir)
        sys.exit(1)

    analyzer = TranscriptAnalyzer()
    transcripts = analyzer.load_directory(transcript_dir)

    if not transcripts:
        logger.error("No valid transcripts found in %s", transcript_dir)
        sys.exit(1)

    logger.info("Loaded %d transcript(s) from %s", len(transcripts), transcript_dir)

    report = analyzer.analyze_batch(transcripts)
    output = analyzer.format_batch_report(report)

    if args.report:
        report_path = Path(args.report)
        report_path.write_text(output, encoding="utf-8")
        logger.info("Report written to %s", report_path)
    else:
        sys.stdout.write(output + "\n")


if __name__ == "__main__":
    main()
