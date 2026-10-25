# -*- coding: utf-8 -*-
"""Tests for independent multi-strategy stock analysis and synthesis."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

import src.analyzer as analyzer_module
from src.analyzer import AnalysisResult, GeminiAnalyzer as RealGeminiAnalyzer


def _result(*, code="600519", name="贵州茅台", score=65, summary="策略独立结论", success=True):
    return AnalysisResult(
        code=code,
        name=name,
        sentiment_score=score,
        trend_prediction="震荡偏强",
        operation_advice="观望",
        confidence_level="中",
        analysis_summary=summary,
        key_points="关键依据",
        success=success,
        error_message=None if success else "mock strategy failure",
    )


def _analyzer(max_agents=4):
    analyzer = RealGeminiAnalyzer.__new__(RealGeminiAnalyzer)
    analyzer._config_override = SimpleNamespace(
        report_language="zh",
        llm_temperature=0.2,
        agent_skill_max_agents=max_agents,
        agent_skill_concurrency=2,
    )
    analyzer._sanitize_hermes_exception_text = lambda exc: str(exc)
    analyzer._build_market_snapshot = lambda context: {"close": "100.00"}
    return analyzer


def test_multi_strategy_runs_each_skill_independently_then_synthesizes(monkeypatch):
    child_calls = []

    class StubChildAnalyzer:
        def __init__(self, *, config, skills):
            self.skill_id = skills[0]

        def analyze(self, context, **kwargs):
            child_calls.append(self.skill_id)
            return _result(
                score=72 if self.skill_id == "bull_trend" else 48,
                summary=f"{self.skill_id} 独立结论",
            )

    monkeypatch.setattr(analyzer_module, "GeminiAnalyzer", StubChildAnalyzer)
    analyzer = _analyzer()
    analyzer._call_litellm = lambda *args, **kwargs: (
        json.dumps({
            "sentiment_score": 62,
            "trend_prediction": "震荡",
            "operation_advice": "观望",
            "decision_type": "hold",
            "confidence_level": "中",
            "analysis_summary": "综合判断：趋势与成长质量存在分歧。",
            "key_points": "综合依据",
            "risk_warning": "关注波动风险",
        }, ensure_ascii=False),
        "mock-synthesis-model",
        {},
    )
    analyzer._parse_response = lambda response_text, code, name: _result(
        code=code,
        name=name,
        score=62,
        summary="综合判断：趋势与成长质量存在分歧。",
    )

    result = analyzer._analyze_multi_strategy(
        {"code": "600519", "stock_name": "贵州茅台"},
        ["bull_trend", "growth_quality"],
    )

    assert sorted(child_calls) == ["bull_trend", "growth_quality"]
    metadata = result.dashboard["multi_strategy_analysis"]
    assert metadata["requested_count"] == 2
    assert metadata["completed_count"] == 2
    assert metadata["failed_count"] == 0
    assert metadata["synthesis_success"] is True
    assert metadata["synthesis_model"] == "mock-synthesis-model"
    assert [item["skill_id"] for item in metadata["strategy_opinions"]] == [
        "bull_trend",
        "growth_quality",
    ]
    assert metadata["conflicts"]
    assert "各策略独立观点" in result.analysis_summary
    assert "观点分歧" in result.analysis_summary


def test_multi_strategy_synthesis_failure_marks_single_strategy_fallback(monkeypatch):
    class StubChildAnalyzer:
        def __init__(self, *, config, skills):
            self.skill_id = skills[0]

        def analyze(self, context, **kwargs):
            return _result(summary=f"{self.skill_id} 独立结论")

    monkeypatch.setattr(analyzer_module, "GeminiAnalyzer", StubChildAnalyzer)
    analyzer = _analyzer()
    analyzer._call_litellm = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthesis unavailable"))

    result = analyzer._analyze_multi_strategy(
        {"code": "600519", "stock_name": "贵州茅台"},
        ["bull_trend", "growth_quality"],
    )

    metadata = result.dashboard["multi_strategy_analysis"]
    assert result.success is True
    assert metadata["synthesis_success"] is False
    assert metadata["synthesis_error"] == "synthesis unavailable"
    assert "回退自单个成功策略" in result.analysis_summary
    assert "各策略独立观点" in result.analysis_summary


def test_multi_strategy_over_limit_is_rejected_without_silent_truncation():
    analyzer = _analyzer(max_agents=4)
    selected = [f"skill_{index}" for index in range(5)]

    result = analyzer._analyze_multi_strategy(
        {"code": "600519", "stock_name": "贵州茅台"},
        selected,
    )

    metadata = result.dashboard["multi_strategy_analysis"]
    assert result.success is False
    assert metadata["requested_count"] == 5
    assert metadata["failed_count"] == 5
    assert metadata["requested_strategy_ids"] == selected
    assert "AGENT_SKILL_MAX_AGENTS=4" in metadata["selection_error"]


def test_analyze_dispatches_multi_skill_requests_to_independent_runner():
    analyzer = RealGeminiAnalyzer.__new__(RealGeminiAnalyzer)
    analyzer._requested_skills = ["bull_trend", "growth_quality", "bull_trend"]
    expected = _result(summary="multi strategy result")
    analyzer._analyze_multi_strategy = Mock(return_value=expected)

    result = RealGeminiAnalyzer.analyze(analyzer, {"code": "600519"})

    assert result is expected
    analyzer._analyze_multi_strategy.assert_called_once_with(
        {"code": "600519"},
        ["bull_trend", "growth_quality"],
        news_context=None,
        progress_callback=None,
        analysis_context_pack_summary=None,
    )
