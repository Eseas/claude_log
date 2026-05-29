"""Tests for the externalized SignalRegistry (signals.yaml)."""

import textwrap

import pytest

from claude_log_organizer.signals import SignalRegistry, get_default_registry


class TestBundledRegistry:
    def test_loads_bundled_signals(self):
        reg = get_default_registry()
        assert len(reg.failure_signals) == 14
        assert len(reg.success_signals) == 8
        assert len(reg.tool_error_signals) == 3

    def test_signals_are_compiled_with_label_and_weight(self):
        reg = SignalRegistry()
        sig = reg.failure_signals[0]
        assert sig.label == "부정 표현"
        assert sig.weight == 0.7
        assert sig.pattern.search("아니 그건 아니야")

    def test_failure_signal_is_case_insensitive(self):
        reg = SignalRegistry()
        # English failure pattern should match regardless of case
        wrong = [s for s in reg.failure_signals if "영문" in s.label][0]
        assert wrong.pattern.search("This is WRONG")

    def test_tool_error_is_case_sensitive(self):
        reg = SignalRegistry()
        traceback_sig = reg.tool_error_signals[0]
        assert traceback_sig.pattern.search("Traceback (most recent call last)")
        # lowercase 'traceback' should NOT match (case-sensitive, preserves original)
        assert not traceback_sig.pattern.search("a traceback happened")


class TestClassifyStep:
    @pytest.mark.parametrize("summary,expected", [
        ("코드를 분석하고 구조를 파악합니다", "analysis"),
        ("이 방법으로 접근하기로 결정", "decision"),
        ("main.py 파일을 수정했습니다", "implementation"),
        ("테스트를 실행하여 검증", "verification"),
        ("작업 완료, 결과 정리", "summary"),
    ])
    def test_classification(self, summary, expected):
        assert get_default_registry().classify_step(summary) == expected

    def test_verification_with_impl_keyword_becomes_implementation(self):
        # "검증" (verify) + "수정" (fix) → reclassified to implementation
        assert get_default_registry().classify_step("검증 후 수정 적용") == "implementation"

    def test_unmatched_defaults_to_analysis(self):
        assert get_default_registry().classify_step("zzzzz qqqqq") == "analysis"


class TestCustomRegistry:
    def test_loads_explicit_path(self, tmp_path):
        custom = tmp_path / "custom_signals.yaml"
        custom.write_text(textwrap.dedent("""
            version: 1
            failure_signals:
              - {pattern: 'nope', label: '커스텀 실패', weight: 0.99}
            success_signals: []
            tool_error_signals: []
            step_classification:
              analysis: 'foo'
        """), encoding="utf-8")
        reg = SignalRegistry(path=custom)
        assert len(reg.failure_signals) == 1
        assert reg.failure_signals[0].label == "커스텀 실패"
        assert reg.failure_signals[0].weight == 0.99

    def test_custom_step_classification(self, tmp_path):
        custom = tmp_path / "s.yaml"
        custom.write_text(textwrap.dedent("""
            version: 1
            failure_signals: []
            success_signals: []
            tool_error_signals: []
            step_classification:
              analysis: 'widget'
        """), encoding="utf-8")
        reg = SignalRegistry(path=custom)
        assert reg.classify_step("inspect the widget") == "analysis"
        assert reg.classify_step("nothing here") == "analysis"  # default fallback
