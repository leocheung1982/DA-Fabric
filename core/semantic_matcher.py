"""
Semantic Matcher — demand-aware supply-demand matching (Section III-D).

DA-Fabric score (default):
  0.30 * indicator + 0.20 * entity + 0.20 * semantic
  + 0.15 * context + 0.10 * mapping + 0.05 * quality
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core.models import (
    DemandMetadata,
    MatchResult,
    ResourceMetadata,
    SemanticMapping,
    load_json,
)

ApplicationDemand = DemandMetadata

_SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer

    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # type: ignore

# DA-Fabric fusion weights
W_INDICATOR = 0.30
W_ENTITY = 0.20
W_SEMANTIC = 0.20
W_CONTEXT = 0.15
W_MAPPING = 0.10
W_QUALITY = 0.05

# Entity-type synonym groups (object_type ↔ entity_type)
ENTITY_SYNONYMS: dict[str, set[str]] = {
    "enterprise": {"enterprise", "market_entity", "business_subject"},
    "license": {"license", "permit", "approval"},
    "penalty": {"penalty", "administrative_sanction", "violation_record"},
    "inspection": {"inspection", "sampling_check", "audit_result"},
    "risk": {"risk", "risk_monitor", "warning_signal"},
}

# Canonical demand indicator → resource field aliases (heterogeneous naming)
FIELD_SYNONYMS: dict[str, list[str]] = {
    "enterprise_name": ["market_entity_name", "business_subject_name"],
    "enterprise_id": ["market_entity_id", "business_subject_id", "credit_code"],
    "market_entity_name": ["enterprise_name", "business_subject_name"],
    "credit_code": ["enterprise_id", "unified_social_credit_code"],
    "license_status": ["permit_status", "approval_status"],
    "license_id": ["permit_id", "approval_id"],
    "penalty_amount": ["administrative_sanction_amount", "violation_fine"],
    "penalty_reason": ["administrative_sanction_reason", "violation_description"],
    "administrative_penalty": ["penalty_amount", "violation_fine"],
    "inspection_result": ["sampling_check_result", "audit_outcome"],
    "inspection_date": ["sampling_check_date", "audit_date"],
    "sampling_result": ["inspection_result", "audit_outcome"],
    "risk_score": ["risk_index", "warning_level_score"],
    "risk_level": ["warning_level", "risk_tier"],
    "risk_index": ["risk_score", "warning_level_score"],
    "violation_type": ["violation_record_type", "noncompliance_category"],
    "handling_status": ["regulatory_handling_status", "case_status"],
}


@dataclass
class MatchOptions:
    """Controls scoring profile and ablation switches."""

    profile: str = "da_fabric"  # keyword | semantic_only | supply_fabric | da_fabric
    use_mapping: bool = True
    use_context: bool = True
    include_application_context: bool = True


class SemanticMatcher:
    """Semantic supply-demand matcher across resource catalog and demands."""

    METHOD_TFIDF = "tfidf"
    METHOD_TRANSFORMER = "sentence_transformer"

    DEFAULT_RESOURCES_PATH = Path(__file__).resolve().parent.parent / "data" / "resources.json"
    DEFAULT_DEMANDS_PATH = Path(__file__).resolve().parent.parent / "data" / "demands.json"
    DEFAULT_MAPPINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "semantic_mappings.json"

    def __init__(
        self,
        method: str = METHOD_TFIDF,
        top_k: int = 10,
        resources_path: Optional[Path | str] = None,
        demands_path: Optional[Path | str] = None,
        mappings_path: Optional[Path | str] = None,
        auto_load: bool = False,
    ) -> None:
        if method == self.METHOD_TRANSFORMER and not _SENTENCE_TRANSFORMERS_AVAILABLE:
            method = self.METHOD_TFIDF
        self.method = method
        self.top_k = top_k
        self._transformer_model: Optional[object] = None

        self._resources: list[ResourceMetadata] = []
        self._demands: list[DemandMetadata] = []
        self._mappings: list[SemanticMapping] = []
        self._mapping_index: dict[str, list[tuple[str, float]]] = {}

        self._resources_path = Path(resources_path) if resources_path else self.DEFAULT_RESOURCES_PATH
        self._demands_path = Path(demands_path) if demands_path else self.DEFAULT_DEMANDS_PATH
        self._mappings_path = Path(mappings_path) if mappings_path else self.DEFAULT_MAPPINGS_PATH

        if auto_load:
            self.load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(
        self,
        resources_path: Optional[Path | str] = None,
        demands_path: Optional[Path | str] = None,
        mappings_path: Optional[Path | str] = None,
    ) -> dict[str, int]:
        counts = {"resources": 0, "demands": 0, "mappings": 0}
        rpath = Path(resources_path) if resources_path else self._resources_path
        if rpath.exists():
            self._resources = load_json(rpath, ResourceMetadata, many=True)
            counts["resources"] = len(self._resources)
        dpath = Path(demands_path) if demands_path else self._demands_path
        if dpath.exists():
            self._demands = load_json(dpath, DemandMetadata, many=True)
            counts["demands"] = len(self._demands)
        mpath = Path(mappings_path) if mappings_path else self._mappings_path
        if mpath.exists():
            self._mappings = load_json(mpath, SemanticMapping, many=True)
            counts["mappings"] = len(self._mappings)
        self._build_mapping_index()
        return counts

    def _build_mapping_index(self) -> None:
        self._mapping_index.clear()
        for mapping in self._mappings:
            src = mapping.source_term.lower()
            tgt = mapping.target_term.lower()
            conf = float(mapping.confidence)
            self._mapping_index.setdefault(src, []).append((tgt, conf))
            if mapping.mapping_type.value in ("equivalent", "similar", "related"):
                self._mapping_index.setdefault(tgt, []).append((src, conf))

    @property
    def resources(self) -> list[ResourceMetadata]:
        return list(self._resources)

    @property
    def demands(self) -> list[DemandMetadata]:
        return list(self._demands)

    @property
    def mappings(self) -> list[SemanticMapping]:
        return list(self._mappings)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resource_field_set(self, resource: ResourceMetadata) -> set[str]:
        return {f.lower() for f in resource.fields + resource.indicators}

    def _expand_field_aliases(self, term: str, use_mapping: bool) -> set[str]:
        """Return exact term plus static field synonyms and optional mapping targets."""
        expanded = {term.lower()}
        for alias in FIELD_SYNONYMS.get(term.lower(), []):
            expanded.add(alias.lower())
        if use_mapping:
            for target, _conf in self._mapping_index.get(term.lower(), []):
                expanded.add(target.lower())
        return expanded

    def _entity_synonyms(self, entity_type: str, use_mapping: bool) -> set[str]:
        base = entity_type.lower()
        group = set(ENTITY_SYNONYMS.get(base, {base}))
        group.add(base)
        if use_mapping:
            for target, _ in self._mapping_index.get(base, []):
                group.add(target.lower())
        return group

    def _demand_text(self, demand: DemandMetadata) -> str:
        parts = [
            demand.task,
            demand.description,
            demand.role,
            demand.application,
            demand.object_type,
            " ".join(demand.indicators),
            " ".join(demand.tags),
            " ".join(str(d) for d in demand.conditions.get("business_domains", [])),
            demand.conditions.get("scenario_type", ""),
        ]
        return " ".join(p for p in parts if p)

    def _resource_text(self, resource: ResourceMetadata) -> str:
        parts = [
            resource.name,
            resource.description,
            resource.business_domain,
            resource.entity_type,
            resource.resource_type,
            " ".join(resource.fields),
            " ".join(resource.indicators),
            " ".join(resource.keywords),
        ]
        return " ".join(p for p in parts if p)

    def _exact_tokens(self, demand: DemandMetadata, resource: ResourceMetadata) -> set[str]:
        """Exact lowercase tokens for KW-Catalog (no synonym expansion)."""
        demand_tokens = set()
        for ind in demand.indicators:
            demand_tokens.add(ind.lower())
        for tag in demand.tags:
            demand_tokens.add(tag.lower())
        demand_tokens.add(demand.object_type.lower())
        resource_tokens = self._resource_field_set(resource)
        for kw in resource.keywords:
            resource_tokens.add(kw.lower())
        resource_tokens.add(resource.entity_type.lower())
        resource_tokens.add(resource.business_domain.lower())
        return demand_tokens & resource_tokens

    def _matched_indicators(
        self,
        demand: DemandMetadata,
        resource: ResourceMetadata,
        *,
        use_mapping: bool = True,
        exact_only: bool = False,
    ) -> list[str]:
        field_set = self._resource_field_set(resource)
        matched: list[str] = []
        for indicator in demand.indicators:
            if indicator.lower() in field_set:
                matched.append(indicator)
                continue
            if exact_only:
                continue
            aliases = self._expand_field_aliases(indicator, use_mapping)
            if aliases & field_set:
                matched.append(indicator)
        return matched

    # ------------------------------------------------------------------
    # Component scorers
    # ------------------------------------------------------------------

    def indicator_score(
        self,
        demand: DemandMetadata,
        resource: ResourceMetadata,
        *,
        use_mapping: bool = True,
        exact_only: bool = False,
    ) -> float:
        """Coverage of demand indicators by resource fields/indicators."""
        if not demand.indicators:
            return 0.0
        matched = self._matched_indicators(
            demand, resource, use_mapping=use_mapping, exact_only=exact_only
        )
        return round(len(matched) / len(demand.indicators), 4)

    def entity_score(
        self,
        demand: DemandMetadata,
        resource: ResourceMetadata,
        *,
        use_mapping: bool = True,
        exact_only: bool = False,
    ) -> float:
        """Object/entity type alignment including synonym groups."""
        if not demand.object_type or not resource.entity_type:
            return 0.0
        if exact_only:
            return 1.0 if demand.object_type.lower() == resource.entity_type.lower() else 0.0
        demand_entities = self._entity_synonyms(demand.object_type, use_mapping)
        resource_entity = resource.entity_type.lower()
        if resource_entity in demand_entities:
            return 1.0
        # Partial token overlap for composite entity labels
        for token in resource_entity.replace("_", " ").split():
            if token in demand_entities:
                return 0.6
        return 0.0

    def mapping_score(
        self,
        demand: DemandMetadata,
        resource: ResourceMetadata,
        *,
        use_mapping: bool = True,
    ) -> float:
        """Semantic mapping alignment between demand terms and resource metadata."""
        if not use_mapping or not self._mapping_index:
            return 0.0
        field_set = self._resource_field_set(resource)
        resource_blob = self._resource_text(resource).lower()
        confidences: list[float] = []

        terms = list(demand.indicators) + [demand.object_type] + demand.tags
        domains = demand.conditions.get("business_domains", [])
        terms.extend(str(d) for d in domains)

        for term in terms:
            if not term:
                continue
            term_l = term.lower()
            for target, conf in self._mapping_index.get(term_l, []):
                if target in field_set or target in resource_blob:
                    confidences.append(conf)
            # Reverse lookup
            for src, targets in self._mapping_index.items():
                if src in field_set or src in resource_blob:
                    for target, conf in targets:
                        if target == term_l:
                            confidences.append(conf)

        if not confidences:
            return 0.0
        return round(min(sum(confidences) / max(len(terms), 1), 1.0), 4)

    def context_score(
        self,
        demand: DemandMetadata,
        resource: ResourceMetadata,
        *,
        use_context: bool = True,
        include_application_context: bool = True,
    ) -> float:
        """Role, application, task, and business-domain contextual alignment."""
        if not use_context:
            return 0.0
        signals: list[float] = []

        domains = demand.conditions.get("business_domains", [])
        if domains:
            signals.append(1.0 if resource.business_domain in domains else 0.0)

        scenario = str(demand.conditions.get("scenario_type", "")).lower()
        if scenario:
            blob = self._resource_text(resource).lower()
            tokens = set(scenario.replace("_", " ").split())
            hits = sum(1 for t in tokens if t in blob)
            signals.append(min(hits / max(len(tokens), 1), 1.0))

        if include_application_context:
            resource_tokens = self._resource_field_set(resource) | {
                t for kw in resource.keywords for t in kw.lower().split("_")
            }
            for attr in (demand.role, demand.application, demand.task):
                if not attr:
                    continue
                attr_tokens = set(str(attr).lower().replace("_", " ").split())
                overlap = len(attr_tokens & resource_tokens)
                if not overlap:
                    overlap = sum(1 for t in attr_tokens if t in self._resource_text(resource).lower())
                signals.append(min(overlap / max(len(attr_tokens), 1), 1.0))

        if not signals:
            return 0.0
        return round(sum(signals) / len(signals), 4)

    def semantic_score(self, demand: DemandMetadata, resource: ResourceMetadata) -> float:
        scores = self._batch_semantic_scores(demand, [resource])
        return scores[0] if scores else 0.0

    def quality_score(self, resource: ResourceMetadata) -> float:
        return round(float(resource.quality_score), 4)

    def keyword_score(self, demand: DemandMetadata, resource: ResourceMetadata) -> float:
        """Legacy alias — exact keyword overlap for KW-Catalog."""
        return self.exact_keyword_score(demand, resource)

    def exact_keyword_score(self, demand: DemandMetadata, resource: ResourceMetadata) -> float:
        """KW-Catalog: exact token overlap only (no synonyms or mappings)."""
        if not demand.indicators:
            overlap = self._exact_tokens(demand, resource)
            return round(min(len(overlap) / 4.0, 1.0), 4)
        matched = self._matched_indicators(demand, resource, use_mapping=False, exact_only=True)
        entity = self.entity_score(demand, resource, use_mapping=False, exact_only=True)
        return round(0.85 * (len(matched) / len(demand.indicators)) + 0.15 * entity, 4)

    def compute_da_fabric_score(
        self,
        indicator: float,
        entity: float,
        semantic: float,
        context: float,
        mapping: float,
        quality: float,
        *,
        use_context: bool = True,
        use_mapping: bool = True,
    ) -> float:
        ctx = context if use_context else 0.0
        mp = mapping if use_mapping else 0.0
        score = (
            W_INDICATOR * indicator
            + W_ENTITY * entity
            + W_SEMANTIC * semantic
            + W_CONTEXT * ctx
            + W_MAPPING * mp
            + W_QUALITY * quality
        )
        return round(min(max(score, 0.0), 1.0), 4)

    def compute_supply_fabric_score(
        self,
        indicator: float,
        entity: float,
        semantic: float,
        domain_context: float,
        quality: float,
    ) -> float:
        """Supply-side baseline: metadata + semantic, no mapping or app-side context."""
        score = (
            0.35 * indicator
            + 0.20 * entity
            + 0.30 * semantic
            + 0.10 * domain_context
            + 0.05 * quality
        )
        return round(min(max(score, 0.0), 1.0), 4)

    def _batch_semantic_scores(
        self,
        demand: DemandMetadata,
        resources: list[ResourceMetadata],
    ) -> list[float]:
        if not resources:
            return []
        if self.method == self.METHOD_TRANSFORMER and _SENTENCE_TRANSFORMERS_AVAILABLE:
            model = self._get_transformer()
            if model is not None:
                texts = [self._demand_text(demand)] + [self._resource_text(r) for r in resources]
                embeddings = model.encode(texts)
                sims = cosine_similarity(embeddings[0:1], embeddings[1:]).flatten()
                return [round(max(float(s), 0.0), 4) for s in sims]

        demand_text = self._demand_text(demand)
        resource_texts = [self._resource_text(r) for r in resources]
        corpus = [demand_text] + resource_texts
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(corpus)
        sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
        return [round(max(float(s), 0.0), 4) for s in sims]

    def _domain_context_only(
        self,
        demand: DemandMetadata,
        resource: ResourceMetadata,
    ) -> float:
        domains = demand.conditions.get("business_domains", [])
        if not domains:
            return 0.5 if demand.object_type == resource.entity_type else 0.0
        return 1.0 if resource.business_domain in domains else 0.0

    def score_pair(
        self,
        demand: DemandMetadata,
        resource: ResourceMetadata,
        *,
        options: Optional[MatchOptions] = None,
        semantic: Optional[float] = None,
    ) -> MatchResult:
        opts = options or MatchOptions()
        sem = semantic if semantic is not None else self.semantic_score(demand, resource)
        qual = self.quality_score(resource)

        if opts.profile == "keyword":
            exact = self.exact_keyword_score(demand, resource)
            return MatchResult(
                demand_id=demand.demand_id,
                resource_id=resource.resource_id,
                score=exact,
                keyword_score=exact,
                indicator_score=exact,
                reason=f"KW-Catalog exact overlap score={exact:.3f}",
                matcher_method="keyword_baseline",
                matched_fields=self._matched_indicators(
                    demand, resource, use_mapping=False, exact_only=True
                ),
            )

        if opts.profile == "semantic_only":
            return MatchResult(
                demand_id=demand.demand_id,
                resource_id=resource.resource_id,
                score=sem,
                semantic_score=sem,
                reason=f"Semantic-only TF-IDF score={sem:.3f}",
                matcher_method="semantic_only_baseline",
                matched_fields=self._matched_indicators(demand, resource, use_mapping=opts.use_mapping),
            )

        ind = self.indicator_score(
            demand,
            resource,
            use_mapping=opts.use_mapping,
            exact_only=opts.profile == "supply_fabric",
        )
        ent = self.entity_score(
            demand,
            resource,
            use_mapping=opts.use_mapping,
            exact_only=opts.profile == "supply_fabric",
        )
        ctx = self.context_score(
            demand,
            resource,
            use_context=opts.use_context,
            include_application_context=opts.include_application_context,
        )
        mp = self.mapping_score(demand, resource, use_mapping=opts.use_mapping)

        if opts.profile == "supply_fabric":
            domain_ctx = self._domain_context_only(demand, resource)
            final = self.compute_supply_fabric_score(ind, ent, sem, domain_ctx, qual)
            matcher_method = "supply_fabric_baseline"
        else:
            final = self.compute_da_fabric_score(
                ind, ent, sem, ctx, mp, qual,
                use_context=opts.use_context,
                use_mapping=opts.use_mapping,
            )
            matcher_method = self.method

        matched = self._matched_indicators(demand, resource, use_mapping=opts.use_mapping)
        reason = (
            f"score={final:.3f}; ind={ind:.2f}; ent={ent:.2f}; sem={sem:.2f}; "
            f"ctx={ctx:.2f}; map={mp:.2f}; qual={qual:.2f}"
        )
        return MatchResult(
            demand_id=demand.demand_id,
            resource_id=resource.resource_id,
            score=final,
            keyword_score=ind,
            indicator_score=ind,
            entity_score=ent,
            semantic_score=sem,
            context_score=ctx,
            mapping_score=mp,
            quality_score=qual,
            reason=reason,
            matcher_method=matcher_method,
            matched_fields=matched,
        )

    def _rank_results(
        self,
        demand: DemandMetadata,
        results: list[MatchResult],
        top_k: int,
    ) -> list[MatchResult]:
        results.sort(key=lambda m: (m.score, m.indicator_score, m.mapping_score), reverse=True)
        for rank, result in enumerate(results[:top_k], start=1):
            result.rank = rank
        return results[:top_k]

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def match(
        self,
        demand: DemandMetadata,
        resources: Optional[list[ResourceMetadata]] = None,
        top_k: Optional[int] = None,
        options: Optional[MatchOptions] = None,
    ) -> list[MatchResult]:
        resource_list = resources if resources is not None else self._resources
        k = top_k if top_k is not None else self.top_k
        opts = options or MatchOptions(profile="da_fabric")
        if not resource_list:
            return []

        semantic_scores = self._batch_semantic_scores(demand, resource_list)
        results = [
            self.score_pair(demand, resource, options=opts, semantic=semantic_scores[idx])
            for idx, resource in enumerate(resource_list)
        ]
        return self._rank_results(demand, results, k)

    def match_all(
        self,
        demands: Optional[list[DemandMetadata]] = None,
        resources: Optional[list[ResourceMetadata]] = None,
        top_k: Optional[int] = None,
        options: Optional[MatchOptions] = None,
    ) -> dict[str, list[MatchResult]]:
        demand_list = demands if demands is not None else self._demands
        resource_list = resources if resources is not None else self._resources
        k = top_k if top_k is not None else self.top_k
        return {
            d.demand_id: self.match(d, resource_list, top_k=k, options=options)
            for d in demand_list
        }

    # ------------------------------------------------------------------
    # Baselines
    # ------------------------------------------------------------------

    def keyword_baseline(
        self,
        demand: DemandMetadata,
        resources: Optional[list[ResourceMetadata]] = None,
        top_k: Optional[int] = None,
    ) -> list[MatchResult]:
        return self.match(
            demand,
            resources,
            top_k=top_k,
            options=MatchOptions(profile="keyword", use_mapping=False, use_context=False),
        )

    def semantic_only_baseline(
        self,
        demand: DemandMetadata,
        resources: Optional[list[ResourceMetadata]] = None,
        top_k: Optional[int] = None,
    ) -> list[MatchResult]:
        return self.match(
            demand,
            resources,
            top_k=top_k,
            options=MatchOptions(profile="semantic_only"),
        )

    def supply_fabric_baseline(
        self,
        demand: DemandMetadata,
        resources: Optional[list[ResourceMetadata]] = None,
        top_k: Optional[int] = None,
    ) -> list[MatchResult]:
        return self.match(
            demand,
            resources,
            top_k=top_k,
            options=MatchOptions(
                profile="supply_fabric",
                use_mapping=False,
                use_context=True,
                include_application_context=False,
            ),
        )

    def da_fabric_match(
        self,
        demand: DemandMetadata,
        resources: Optional[list[ResourceMetadata]] = None,
        top_k: Optional[int] = None,
        *,
        use_mapping: bool = True,
        use_context: bool = True,
        include_application_context: bool = True,
    ) -> list[MatchResult]:
        return self.match(
            demand,
            resources,
            top_k=top_k,
            options=MatchOptions(
                profile="da_fabric",
                use_mapping=use_mapping,
                use_context=use_context,
                include_application_context=include_application_context,
            ),
        )

    # ------------------------------------------------------------------
    # Ground-truth helper (used by data generation)
    # ------------------------------------------------------------------

    def relevance_score_for_labeling(
        self,
        demand: DemandMetadata,
        resource: ResourceMetadata,
    ) -> float:
        """Mapping-aware relevance score for synthetic ground-truth labeling."""
        sem = self.semantic_score(demand, resource)
        ind = self.indicator_score(demand, resource, use_mapping=True)
        ent = self.entity_score(demand, resource, use_mapping=True)
        ctx = self.context_score(demand, resource, use_context=True, include_application_context=True)
        mp = self.mapping_score(demand, resource, use_mapping=True)
        qual = self.quality_score(resource)
        return self.compute_da_fabric_score(ind, ent, sem, ctx, mp, qual)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _get_transformer(self):
        if self._transformer_model is None and _SENTENCE_TRANSFORMERS_AVAILABLE:
            self._transformer_model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._transformer_model

    def apply_weight_adjustments(self, adjustments: dict[str, float]) -> None:
        """Legacy hook for feedback optimizer weight tweaks."""
        _ = adjustments

    def batch_match(
        self,
        demands: list[DemandMetadata],
        resources: list[ResourceMetadata],
    ) -> dict[str, list[MatchResult]]:
        return self.match_all(demands, resources)

    @staticmethod
    def available_methods() -> list[str]:
        methods = [SemanticMatcher.METHOD_TFIDF]
        if _SENTENCE_TRANSFORMERS_AVAILABLE:
            methods.append(SemanticMatcher.METHOD_TRANSFORMER)
        return methods

    @staticmethod
    def transformer_available() -> bool:
        return _SENTENCE_TRANSFORMERS_AVAILABLE
