"""
Tests for the heuristic recommender. The recommender is a pure function of
(Dataset, ScenarioMetrics-before, ScenarioMetrics-after, MetricsDelta) — it
needs no API key and no I/O. These tests exercise the underutilization rule
and the produced RouteRecommendation shape.
"""

from app.config import settings
from app.models.recommendation import RouteRecommendation
from app.services import heuristic_recommender
from app.services.metrics_service import compute_after, compute_before, compute_delta


def test_recommender_produces_a_valid_RouteRecommendation(small_dataset):
    before = compute_before(small_dataset)
    after = compute_after(small_dataset)
    delta = compute_delta(before, after)

    rec = heuristic_recommender.recommend(small_dataset, before, after, delta)

    assert isinstance(rec, RouteRecommendation)
    assert rec.dataset_id == "test_ds"
    assert 0.0 <= rec.confidence_score <= 1.0
    assert rec.model_used == "heuristic (no LLM)"
    assert rec.analysis_summary
    assert rec.explanation


def test_recommender_flags_underutilized_routes(small_dataset):
    before = compute_before(small_dataset)
    after = compute_after(small_dataset)
    delta = compute_delta(before, after)

    rec = heuristic_recommender.recommend(small_dataset, before, after, delta)

    # R1 (18/72 = 0.25) and R2 (5/72 = 0.07) are both under the 0.50 threshold
    assert any("R1" in s for s in rec.inefficiencies)
    assert any("R2" in s for s in rec.inefficiencies)


def test_recommender_emits_one_eliminate_edit_per_eliminated_route(small_dataset):
    before = compute_before(small_dataset)
    after = compute_after(small_dataset)
    delta = compute_delta(before, after)

    rec = heuristic_recommender.recommend(small_dataset, before, after, delta)

    eliminate_actions = [e for e in rec.route_edits if e.action == "eliminate"]
    affected = {r for e in eliminate_actions for r in e.affected_routes}
    assert affected == set(small_dataset.optimized_scenario.eliminated_routes)


def test_recommender_threshold_is_read_from_config(small_dataset, monkeypatch):
    """
    With threshold above every route's load factor, both routes are flagged.
    With threshold at 0.0, no route is flagged. Proves the rule reads config
    rather than hardcoding 0.5.
    """
    before = compute_before(small_dataset)
    after = compute_after(small_dataset)
    delta = compute_delta(before, after)

    monkeypatch.setattr(settings, "load_factor_underutilized", 0.99)
    rec_high = heuristic_recommender.recommend(small_dataset, before, after, delta)
    assert any("R1" in s for s in rec_high.inefficiencies)
    assert any("R2" in s for s in rec_high.inefficiencies)

    monkeypatch.setattr(settings, "load_factor_underutilized", 0.0)
    rec_low = heuristic_recommender.recommend(small_dataset, before, after, delta)
    assert not any("operates at only" in s for s in rec_low.inefficiencies)


def test_recommender_expected_improvements_have_three_metrics(small_dataset):
    before = compute_before(small_dataset)
    after = compute_after(small_dataset)
    delta = compute_delta(before, after)

    rec = heuristic_recommender.recommend(small_dataset, before, after, delta)

    metrics = {ei.metric for ei in rec.expected_improvements}
    assert "Average bus utilization" in metrics
    assert "Total daily distance" in metrics
    assert "Fleet size" in metrics
