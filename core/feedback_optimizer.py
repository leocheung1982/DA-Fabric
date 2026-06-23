"""
Feedback Optimizer — collects feedback and adjusts matching relevance
via resource usage boosts and semantic mapping confidence (Section III-H).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.models import (
    FeedbackAction,
    FeedbackEvent,
    MatchResult,
    OptimizationSnapshot,
    SemanticMapping,
    load_json,
    save_json,
)
from core.semantic_matcher import SemanticMatcher

DEFAULT_FEEDBACK_PATH = Path(__file__).resolve().parent.parent / "data" / "feedback_events.json"
DEFAULT_MAPPINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "semantic_mappings.json"

ACTION_WEIGHTS: dict[FeedbackAction, float] = {
    FeedbackAction.ADOPTED: 0.15,
    FeedbackAction.CLICKED: 0.08,
    FeedbackAction.VIEWED: 0.04,
    FeedbackAction.EXPORTED: 0.10,
    FeedbackAction.IGNORED: -0.08,
    FeedbackAction.REJECTED: -0.12,
}


class FeedbackOptimizer:
    """Closed-loop optimization based on user and system feedback."""

    def __init__(
        self,
        matcher: Optional[SemanticMatcher] = None,
        data_path: Optional[Path | str] = None,
        mappings_path: Optional[Path | str] = None,
    ) -> None:
        self.matcher = matcher or SemanticMatcher(auto_load=True)
        self._data_path = Path(data_path) if data_path else DEFAULT_FEEDBACK_PATH
        self._mappings_path = Path(mappings_path) if mappings_path else DEFAULT_MAPPINGS_PATH

        self._feedback: list[FeedbackEvent] = []
        self._snapshots: list[OptimizationSnapshot] = []
        self._resource_boost: dict[str, float] = {}
        self._mapping_confidence: dict[str, float] = {}
        self._mappings: list[SemanticMapping] = []

        self._load_mappings_index()

    def _load_mappings_index(self) -> None:
        if self._mappings_path.exists():
            self._mappings = load_json(self._mappings_path, SemanticMapping, many=True)
            for mapping in self._mappings:
                self._mapping_confidence[mapping.mapping_id] = mapping.confidence

    # ------------------------------------------------------------------
    # Feedback API
    # ------------------------------------------------------------------

    def feedback_weight(self, action: FeedbackAction | str) -> float:
        """Return the weight associated with a feedback action."""
        if isinstance(action, str):
            try:
                action = FeedbackAction(action)
            except ValueError:
                return 0.0
        return ACTION_WEIGHTS.get(action, 0.0)

    def add_feedback(self, feedback: FeedbackEvent) -> FeedbackEvent:
        """
        Record feedback and update in-memory resource boosts and mapping confidence.
        """
        self._feedback.append(feedback)
        weight = self.feedback_weight(feedback.action)

        if feedback.resource_id:
            current = self._resource_boost.get(feedback.resource_id, 0.0)
            self._resource_boost[feedback.resource_id] = round(current + weight, 4)

        self._update_mapping_confidence(feedback, weight)
        return feedback

    def _update_mapping_confidence(self, feedback: FeedbackEvent, weight: float) -> None:
        """Adjust semantic mapping confidence based on feedback."""
        if not self._mappings:
            return

        for mapping in self._mappings:
            related = False
            if feedback.resource_id and mapping.source_term.lower() in feedback.resource_id.lower():
                related = True
            if feedback.demand_id and mapping.mapping_id.startswith("map-"):
                frac = abs(hash(feedback.demand_id + mapping.mapping_id)) % 100
                related = related or frac < 15

            if related:
                current = self._mapping_confidence.get(mapping.mapping_id, mapping.confidence)
                updated = max(0.0, min(1.0, current + weight * 0.5))
                self._mapping_confidence[mapping.mapping_id] = round(updated, 4)

    def get_resource_usage_boost(self, resource_id: str) -> float:
        """Return accumulated relevance boost for a resource from feedback."""
        return self._resource_boost.get(resource_id, 0.0)

    def get_mapping_confidence(self, mapping_id: str) -> float:
        """Return current in-memory confidence for a semantic mapping."""
        return self._mapping_confidence.get(mapping_id, 0.0)

    def apply_feedback_boost(
        self,
        match_results: list[MatchResult],
    ) -> list[MatchResult]:
        """Apply resource usage boosts to matching scores and re-rank."""
        boosted: list[MatchResult] = []
        for result in match_results:
            boost = self.get_resource_usage_boost(result.resource_id)
            new_score = min(1.0, round(result.score + boost, 4))
            reason_suffix = f"; feedback_boost=+{boost:.3f}" if boost else ""
            boosted.append(
                result.model_copy(
                    update={
                        "score": new_score,
                        "reason": result.reason + reason_suffix,
                    }
                )
            )
        boosted.sort(key=lambda m: (m.score, m.mapping_score, m.indicator_score), reverse=True)
        for rank, result in enumerate(boosted, start=1):
            result.rank = rank
        return boosted

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load_from_file(self, path: Optional[Path | str] = None) -> int:
        """Load feedback events and apply boosts."""
        file_path = Path(path) if path else self._data_path
        if not file_path.exists():
            return 0

        records = load_json(file_path)
        self._feedback.clear()
        self._resource_boost.clear()

        for item in records:
            self.add_feedback(FeedbackEvent.model_validate(item))
        return len(self._feedback)

    def save_to_file(self, path: Optional[Path | str] = None) -> None:
        """Persist feedback events to JSON."""
        file_path = Path(path) if path else self._data_path
        payload = [fb.model_dump(mode="json") for fb in self._feedback]
        save_json(file_path, payload)

    # ------------------------------------------------------------------
    # Legacy optimization loop
    # ------------------------------------------------------------------

    def record_feedback(self, feedback: FeedbackEvent) -> FeedbackEvent:
        """Legacy alias for add_feedback."""
        return self.add_feedback(feedback)

    def optimize(self, iteration: int = 1) -> OptimizationSnapshot:
        """Adjust matcher weights based on accumulated feedback actions."""
        if not self._feedback:
            snapshot = OptimizationSnapshot(
                iteration=iteration,
                matcher_method=self.matcher.method,
                avg_rating=0.0,
                avg_relevance=0.0,
            )
            self._snapshots.append(snapshot)
            return snapshot

        avg_rating = sum(f.rating for f in self._feedback) / len(self._feedback)
        avg_relevance = sum(f.relevance_score for f in self._feedback) / len(self._feedback)

        action_delta = sum(self.feedback_weight(f.action) for f in self._feedback) / len(self._feedback)
        adjustments: dict[str, float] = {}
        if action_delta > 0.02:
            adjustments = {"fields": 0.04, "semantic": 0.03}
        elif action_delta < -0.02:
            adjustments = {"description": 0.05, "tags": 0.04}
        else:
            adjustments = {"tags": 0.02, "fields": 0.02}

        self.matcher.apply_weight_adjustments(adjustments)

        snapshot = OptimizationSnapshot(
            iteration=iteration,
            matcher_method=self.matcher.method,
            avg_rating=round(avg_rating, 4),
            avg_relevance=round(avg_relevance, 4),
            weight_adjustments=adjustments,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def run_iterations(self, n: int = 3) -> list[OptimizationSnapshot]:
        return [self.optimize(iteration=i + 1) for i in range(n)]

    @property
    def feedback_count(self) -> int:
        return len(self._feedback)

    @property
    def snapshots(self) -> list[OptimizationSnapshot]:
        return list(self._snapshots)

    @property
    def resource_boosts(self) -> dict[str, float]:
        return dict(self._resource_boost)

    @property
    def mapping_confidences(self) -> dict[str, float]:
        return dict(self._mapping_confidence)

    def summary(self) -> dict:
        if not self._feedback:
            return {"count": 0, "avg_rating": 0.0, "avg_relevance": 0.0}
        return {
            "count": len(self._feedback),
            "avg_rating": round(sum(f.rating for f in self._feedback) / len(self._feedback), 4),
            "avg_relevance": round(
                sum(f.relevance_score for f in self._feedback) / len(self._feedback), 4
            ),
            "optimization_iterations": len(self._snapshots),
            "boosted_resources": len(self._resource_boost),
            "adjusted_mappings": len(self._mapping_confidence),
        }
