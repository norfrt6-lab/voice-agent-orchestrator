"""Tests for the evaluation framework: metrics, failure detection, and auto-improver."""

from pathlib import Path

import pytest

from src.evaluation.auto_improver import AutoImprover
from src.evaluation.failure_detector import FailureDetector, FailurePattern, FailureSeverity
from src.evaluation.metrics import EvalMetrics, MetricsCalculator
from src.evaluation.transcript_analyzer import TranscriptAnalyzer
from src.schemas.conversation_schema import (
    CallOutcome,
    Speaker,
)
from tests.conftest import make_transcript, make_transcript_with_turns, make_turn


class TestMetricsCalculator:
    def setup_method(self):
        self.calc = MetricsCalculator()

    def test_successful_booking_metrics(self):
        transcript = make_transcript(
            outcome=CallOutcome.BOOKING_MADE,
            slots={
                "customer_name": "John",
                "customer_phone": "0412345678",
                "service_type": "plumbing",
                "preferred_date": "2025-03-18",
                "preferred_time": "10:00",
                "customer_address": "42 Oak Ave",
            },
        )
        metrics = self.calc.calculate(transcript)
        assert metrics.success_rate == 1.0
        assert metrics.first_call_resolution == 1.0
        assert metrics.containment_rate == 1.0
        assert metrics.slot_fill_rate == 1.0

    def test_failed_booking_metrics(self):
        transcript = make_transcript(
            outcome=CallOutcome.BOOKING_FAILED,
            slots={"customer_name": "John", "customer_phone": "0412345678"},
        )
        metrics = self.calc.calculate(transcript)
        assert metrics.success_rate == 0.0
        assert metrics.slot_fill_rate == pytest.approx(2 / 6)

    def test_escalated_call_metrics(self):
        transcript = make_transcript(outcome=CallOutcome.ESCALATED)
        metrics = self.calc.calculate(transcript)
        assert metrics.containment_rate == 0.0
        assert metrics.escalation_rate == 1.0

    def test_info_provided_metrics(self):
        transcript = make_transcript(outcome=CallOutcome.INFO_PROVIDED)
        metrics = self.calc.calculate(transcript)
        assert metrics.first_call_resolution == 1.0
        assert metrics.success_rate == 0.0

    def test_error_rate_calculation(self):
        transcript = make_transcript(error_count=2)
        metrics = self.calc.calculate(transcript)
        assert metrics.error_rate == pytest.approx(2 / 3)  # 2 errors / 3 turns

    def test_batch_metrics_averaging(self):
        t1 = make_transcript(outcome=CallOutcome.BOOKING_MADE)
        t2 = make_transcript(call_id="TEST-002", outcome=CallOutcome.BOOKING_FAILED)
        metrics = self.calc.calculate_batch([t1, t2])
        assert metrics.success_rate == pytest.approx(0.5)

    def test_format_report_produces_output(self):
        transcript = make_transcript()
        metrics = self.calc.calculate(transcript)
        report = self.calc.format_report(metrics)
        assert "VOICE AGENT EVALUATION REPORT" in report
        assert "Success rate" in report

    def test_empty_batch_returns_default_metrics(self):
        metrics = self.calc.calculate_batch([])
        assert metrics.success_rate == 0.0


class TestFailureDetector:
    def setup_method(self):
        self.detector = FailureDetector()

    def test_detect_repeated_slot_failure(self):
        turns = [
            ("agent", "What is your name?"),
            ("user", "John"),
            ("agent", "Could you tell me your name again?"),
            ("user", "John Smith"),
            ("agent", "Can you confirm your name please?"),
            ("user", "John Smith!"),
        ]
        transcript = make_transcript_with_turns(turns)
        failures = self.detector.detect_all(transcript)
        # 3 mentions of "name" with question keywords
        pattern_types = [f.pattern for f in failures]
        assert FailurePattern.REPEATED_SLOT_FAILURE in pattern_types

    def test_detect_confirmation_loop(self):
        turns = [
            ("agent", "Here's what I have. Does everything sound correct?"),
            ("user", "Hmm not sure"),
            ("agent", "Let me confirm your details again. Does everything sound correct?"),
            ("user", "I think so"),
            ("agent", "Here's what I have one more time. Does everything sound correct?"),
            ("user", "Yes"),
        ]
        transcript = make_transcript_with_turns(turns)
        failures = self.detector.detect_all(transcript)
        pattern_types = [f.pattern for f in failures]
        assert FailurePattern.CONFIRMATION_LOOP in pattern_types

    def test_detect_caller_frustration_unaddressed(self):
        turns = [
            ("user", "This is ridiculous, I already told you my name"),
            ("agent", "What is your phone number?"),
        ]
        transcript = make_transcript_with_turns(turns)
        failures = self.detector.detect_all(transcript)
        pattern_types = [f.pattern for f in failures]
        assert FailurePattern.CALLER_FRUSTRATION in pattern_types

    def test_frustration_addressed_not_flagged(self):
        turns = [
            ("user", "This is ridiculous"),
            ("agent", "I'm sorry about that. Let me transfer you to a team member."),
        ]
        transcript = make_transcript_with_turns(turns)
        failures = self.detector.detect_all(transcript)
        frustration_failures = [
            f for f in failures if f.pattern == FailurePattern.CALLER_FRUSTRATION
        ]
        assert len(frustration_failures) == 0

    def test_detect_hallucinated_info(self):
        turns = [
            ("agent", "We guarantee all our work for 10 years."),
            ("user", "Great!"),
        ]
        transcript = make_transcript_with_turns(turns)
        failures = self.detector.detect_all(transcript)
        pattern_types = [f.pattern for f in failures]
        assert FailurePattern.HALLUCINATED_INFO in pattern_types

    def test_detect_incomplete_booking(self):
        transcript = make_transcript(
            outcome=CallOutcome.CALLER_HUNG_UP,
            slots={
                "customer_name": "John",
                "customer_phone": "0412345678",
                "service_type": "plumbing",
                "preferred_date": "2025-03-18",
            },
        )
        failures = self.detector.detect_all(transcript)
        pattern_types = [f.pattern for f in failures]
        assert FailurePattern.INCOMPLETE_BOOKING in pattern_types

    def test_detect_wrong_agent_handoff(self):
        transcript = make_transcript(
            agents_used=["IntakeAgent", "BookingAgent", "InfoAgent", "EscalationAgent"]
        )
        failures = self.detector.detect_all(transcript)
        pattern_types = [f.pattern for f in failures]
        assert FailurePattern.WRONG_AGENT_HANDOFF in pattern_types

    def test_detect_slow_response(self):
        turns = [
            make_turn(Speaker.AGENT, "Processing...", 0.0, response_time_ms=12000),
        ]
        transcript = make_transcript(turns=turns)
        failures = self.detector.detect_all(transcript)
        pattern_types = [f.pattern for f in failures]
        assert FailurePattern.SLOW_RESPONSE in pattern_types

    def test_no_failures_on_clean_transcript(self):
        turns = [
            make_turn(Speaker.AGENT, "Hello, how can I help?", 0.0, agent_id="IntakeAgent"),
            make_turn(Speaker.USER, "I need a plumber.", 3.0),
            make_turn(Speaker.AGENT, "I'll book that for you.", 5.0, agent_id="BookingAgent"),
        ]
        transcript = make_transcript(
            turns=turns,
            agents_used=["IntakeAgent", "BookingAgent"],
        )
        failures = self.detector.detect_all(transcript)
        # Should be minimal or no failures on a clean transcript
        critical = [f for f in failures if f.severity == FailureSeverity.CRITICAL]
        assert len(critical) == 0


class TestAutoImprover:
    def setup_method(self):
        self.improver = AutoImprover()

    def test_suggestions_generated_for_known_patterns(self):
        from src.evaluation.failure_detector import DetectedFailure

        failures = [
            DetectedFailure(
                pattern=FailurePattern.REPEATED_SLOT_FAILURE,
                severity=FailureSeverity.HIGH,
                evidence="Asked for name 3 times",
            ),
            DetectedFailure(
                pattern=FailurePattern.CALLER_FRUSTRATION,
                severity=FailureSeverity.CRITICAL,
                evidence="Caller said 'ridiculous'",
            ),
        ]
        suggestions = self.improver.suggest_improvements(failures)
        assert len(suggestions) == 2
        # Critical should come first
        assert suggestions[0].priority == "critical"

    def test_deduplication_of_same_pattern(self):
        from src.evaluation.failure_detector import DetectedFailure

        failures = [
            DetectedFailure(
                pattern=FailurePattern.HALLUCINATED_INFO,
                severity=FailureSeverity.HIGH,
                evidence="Used 'guarantee'",
            ),
            DetectedFailure(
                pattern=FailurePattern.HALLUCINATED_INFO,
                severity=FailureSeverity.HIGH,
                evidence="Used 'warranty'",
            ),
        ]
        suggestions = self.improver.suggest_improvements(failures)
        assert len(suggestions) == 1

    def test_format_suggestions_output(self):
        from src.evaluation.failure_detector import DetectedFailure

        failures = [
            DetectedFailure(
                pattern=FailurePattern.SCOPE_VIOLATION,
                severity=FailureSeverity.HIGH,
                evidence="Agent discussed competitor",
            ),
        ]
        suggestions = self.improver.suggest_improvements(failures)
        output = self.improver.format_suggestions(suggestions)
        assert "PROMPT IMPROVEMENT SUGGESTIONS" in output
        assert "scope_violation" in output

    def test_empty_failures_returns_clean_message(self):
        suggestions = self.improver.suggest_improvements([])
        output = self.improver.format_suggestions(suggestions)
        assert "No improvement suggestions" in output


class TestTranscriptAnalyzer:
    def setup_method(self):
        self.analyzer = TranscriptAnalyzer()

    def test_single_analysis(self):
        transcript = make_transcript()
        analysis = self.analyzer.analyze(transcript)
        assert analysis.call_id == "TEST-001"
        assert isinstance(analysis.metrics, EvalMetrics)
        assert isinstance(analysis.failures, list)
        assert isinstance(analysis.suggestions, list)

    def test_batch_analysis(self):
        t1 = make_transcript()
        t2 = make_transcript(call_id="TEST-002", outcome=CallOutcome.ESCALATED)
        report = self.analyzer.analyze_batch([t1, t2])
        assert report.total_calls == 2
        assert len(report.analyses) == 2

    def test_batch_report_formatting(self):
        t1 = make_transcript()
        report = self.analyzer.analyze_batch([t1])
        output = self.analyzer.format_batch_report(report)
        assert "ANALYZED: 1 conversations" in output
        assert "PER-CALL BREAKDOWN" in output

    def test_load_from_sample_transcripts(self):
        sample_dir = Path("sample_transcripts")
        if sample_dir.exists():
            transcripts = self.analyzer.load_directory(sample_dir)
            assert len(transcripts) >= 1
            report = self.analyzer.analyze_batch(transcripts)
            assert report.total_calls == len(transcripts)


class TestSampleTranscriptEval:
    """Run evaluation on actual sample transcripts."""

    def test_eval_sample_transcripts(self):
        analyzer = TranscriptAnalyzer()
        sample_dir = Path("sample_transcripts")
        if not sample_dir.exists():
            pytest.skip("sample_transcripts directory not found")

        transcripts = analyzer.load_directory(sample_dir)
        assert len(transcripts) == 5

        report = analyzer.analyze_batch(transcripts)
        assert report.total_calls == 5

        # At least some should succeed
        success_count = sum(1 for a in report.analyses if a.metrics.success_rate > 0)
        assert success_count >= 2

        output = analyzer.format_batch_report(report)
        assert len(output) > 100  # Non-trivial output
