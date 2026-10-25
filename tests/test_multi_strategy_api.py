# -*- coding: utf-8 -*-
"""Contract tests for the configurable multi-strategy execution limit."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from api.v1.endpoints.analysis import trigger_analysis
from api.v1.endpoints.agent import _build_skills_response
from api.v1.schemas.analysis import AnalyzeRequest


def test_analysis_api_rejects_strategy_count_above_configured_limit():
    request = AnalyzeRequest(
        stock_code="600519",
        skills=["bull_trend", "growth_quality", "hot_theme"],
    )

    with pytest.raises(HTTPException) as error:
        trigger_analysis(request, SimpleNamespace(agent_skill_max_agents=2))

    assert error.value.status_code == 400
    assert "AGENT_SKILL_MAX_AGENTS" in str(error.value.detail)
    assert "3" in str(error.value.detail)
    assert "2" in str(error.value.detail)


@patch("src.agent.skills.defaults.get_primary_default_skill_id", return_value="bull_trend")
@patch("src.agent.factory.get_skill_manager")
def test_agent_skills_response_exposes_configured_maximum(
    mock_get_skill_manager,
    _mock_default_skill,
):
    mock_get_skill_manager.return_value.list_skills.return_value = [
        SimpleNamespace(
            name="bull_trend",
            display_name="多头趋势",
            description="趋势分析",
            user_invocable=True,
            default_priority=1,
        ),
        SimpleNamespace(
            name="growth_quality",
            display_name="成长质量",
            description="成长股分析",
            user_invocable=True,
            default_priority=2,
        ),
    ]

    response = _build_skills_response(SimpleNamespace(agent_skill_max_agents=8))

    assert response.max_agents == 8
    assert response.default_skill_id == "bull_trend"
    assert [skill.id for skill in response.skills] == ["bull_trend", "growth_quality"]
