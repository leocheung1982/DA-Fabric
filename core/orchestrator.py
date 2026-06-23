"""
Orchestrator — cross-node task orchestration across platform, source,
and application fabric nodes (Section III-F).
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional, Union

from core.models import (
    DemandMetadata,
    ExecutionResult,
    PlanTask,
    TaskPlan,
    TaskStatus,
    VirtualView,
)
from core.registry import NodeRegistry

ApplicationDemand = DemandMetadata
OrchestrationTask = PlanTask
TaskOrchestrationPlan = TaskPlan

# Latency bounds (ms) by node type
LATENCY_BOUNDS = {
    "platform": (20, 80),
    "source": (60, 150),
    "application": (40, 120),
    "unknown": (30, 130),
}

MERGE_BASE_MS = 15.0
MERGE_PER_RESULT_MS = 2.0


class TaskOrchestrator:
    """Simulates cross-node execution of a virtual view."""

    def __init__(self, registry: Optional[NodeRegistry] = None) -> None:
        self.registry = registry

    # ------------------------------------------------------------------
    # Deterministic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stable_fraction(*parts: Any) -> float:
        """Return a deterministic fraction in [0, 1) from input parts."""
        payload = "|".join(str(p) for p in parts)
        digest = hashlib.md5(payload.encode()).hexdigest()
        return int(digest[:8], 16) / 0xFFFFFFFF

    def _node_type(self, node_id: str) -> str:
        if self.registry:
            node = self.registry.get_node(node_id)
            if node:
                return node.node_type.value
        if node_id.startswith("plat-"):
            return "platform"
        if node_id.startswith("src-"):
            return "source"
        if node_id.startswith("app-"):
            return "application"
        return "unknown"

    def _task_latency_ms(
        self,
        task_id: str,
        node_id: str,
        operation: str,
    ) -> float:
        """Deterministic simulated latency between 20–150 ms by node type."""
        node_type = self._node_type(node_id)
        lo, hi = LATENCY_BOUNDS.get(node_type, LATENCY_BOUNDS["unknown"])
        frac = self._stable_fraction(task_id, node_id, operation, node_type)
        return round(lo + frac * (hi - lo), 2)

    def _task_dict(self, task: Union[dict, PlanTask]) -> dict:
        if isinstance(task, PlanTask):
            resource_id = task.result.get("resource_id", "")
            params = task.result.get("params", {})
            return {
                "task_id": task.task_id,
                "node_id": task.target_node_id,
                "resource_id": resource_id,
                "operation": task.task_type or "query",
                "params": params,
            }
        return task

    # ------------------------------------------------------------------
    # Task plan
    # ------------------------------------------------------------------

    def create_task_plan(self, view: VirtualView) -> TaskPlan:
        """Build a TaskPlan from a VirtualView execution plan."""
        exec_plan = view.execution_plan or {}
        raw_tasks: list[dict] = exec_plan.get("tasks", [])
        execution_mode = exec_plan.get("execution_mode", "sequential")

        plan_tasks: list[PlanTask] = []
        for raw in raw_tasks:
            operation = raw.get("operation", "query")
            node_id = raw.get("node_id", "")
            task_id = raw.get("task_id", f"T{len(plan_tasks) + 1}")
            latency = self._task_latency_ms(task_id, node_id, operation)
            plan_tasks.append(
                PlanTask(
                    task_id=task_id,
                    task_type=operation,
                    target_node_id=node_id,
                    description=f"{operation} on {raw.get('resource_id', 'resource')}",
                    estimated_duration_ms=latency,
                    result={
                        "resource_id": raw.get("resource_id", ""),
                        "params": raw.get("params", {}),
                    },
                )
            )

        dependencies = exec_plan.get("dependencies")
        if not dependencies:
            dependencies = self._default_dependencies(raw_tasks, execution_mode)

        total_estimated = self._estimate_total_latency(
            plan_tasks, execution_mode, exec_plan.get("node_groups", {})
        )

        return TaskPlan(
            view_id=view.view_id,
            demand_id=view.demand_id,
            tasks=plan_tasks,
            dependencies=dependencies,
            execution_mode=execution_mode,
            total_estimated_ms=round(total_estimated, 2),
        )

    def _default_dependencies(
        self,
        raw_tasks: list[dict],
        execution_mode: str,
    ) -> dict[str, list[str]]:
        """Build dependency map; sequential mode chains tasks, parallel has none."""
        deps: dict[str, list[str]] = {}
        if execution_mode == "sequential":
            prev: Optional[str] = None
            for raw in raw_tasks:
                tid = raw.get("task_id", "")
                if prev:
                    deps[tid] = [prev]
                else:
                    deps[tid] = []
                prev = tid
        else:
            for raw in raw_tasks:
                deps[raw.get("task_id", "")] = []
        return deps

    def _estimate_total_latency(
        self,
        tasks: list[PlanTask],
        execution_mode: str,
        node_groups: dict[str, list[str]],
    ) -> float:
        if not tasks:
            return 0.0
        latencies = {t.task_id: t.estimated_duration_ms for t in tasks}
        if execution_mode == "sequential":
            exec_ms = sum(latencies.values())
        else:
            per_node: list[float] = []
            if node_groups:
                for task_ids in node_groups.values():
                    per_node.append(sum(latencies.get(tid, 0.0) for tid in task_ids))
            else:
                per_node = list(latencies.values())
            exec_ms = max(per_node) if per_node else 0.0
        merge_ms = MERGE_BASE_MS + MERGE_PER_RESULT_MS * len(tasks)
        return exec_ms + merge_ms

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def simulate_local_task(self, task: Union[dict, PlanTask]) -> dict:
        """Simulate execution of a single local task on a fabric node."""
        raw = self._task_dict(task)
        task_id = raw.get("task_id", "")
        node_id = raw.get("node_id", "")
        operation = raw.get("operation", "query")
        resource_id = raw.get("resource_id", "")
        latency_ms = self._task_latency_ms(task_id, node_id, operation)

        row_frac = self._stable_fraction(task_id, resource_id, "rows")
        rows = int(100 + row_frac * 900)

        return {
            "task_id": task_id,
            "node_id": node_id,
            "resource_id": resource_id,
            "operation": operation,
            "latency_ms": latency_ms,
            "status": "completed",
            "rows": rows,
            "params": raw.get("params", {}),
        }

    def merge_results(self, local_results: list[dict]) -> dict:
        """Merge local task results into a unified result summary."""
        merge_latency_ms = round(
            MERGE_BASE_MS + MERGE_PER_RESULT_MS * len(local_results), 2
        )
        total_rows = sum(r.get("rows", 0) for r in local_results)
        resources = sorted({r.get("resource_id", "") for r in local_results if r.get("resource_id")})
        nodes = sorted({r.get("node_id", "") for r in local_results if r.get("node_id")})

        return {
            "status": "success" if local_results else "empty",
            "merged_records": total_rows,
            "merge_latency_ms": merge_latency_ms,
            "source_task_count": len(local_results),
            "invoked_nodes": nodes,
            "invoked_resources": resources,
            "task_results": [
                {
                    "task_id": r.get("task_id"),
                    "resource_id": r.get("resource_id"),
                    "rows": r.get("rows", 0),
                    "latency_ms": r.get("latency_ms", 0),
                }
                for r in local_results
            ],
        }

    def _compute_execution_latency(
        self,
        local_results: list[dict],
        execution_mode: str,
        node_groups: dict[str, list[str]],
        merge_latency_ms: float,
    ) -> float:
        if not local_results:
            return merge_latency_ms

        latencies = {r["task_id"]: r["latency_ms"] for r in local_results}

        if execution_mode == "sequential":
            exec_ms = sum(latencies.values())
        else:
            per_node: list[float] = []
            if node_groups:
                for task_ids in node_groups.values():
                    per_node.append(sum(latencies.get(tid, 0.0) for tid in task_ids))
            else:
                per_node = list(latencies.values())
            exec_ms = max(per_node) if per_node else 0.0

        return round(exec_ms + merge_latency_ms, 2)

    def _redundant_invocation_ratio(
        self,
        invoked_resources: list[str],
        ground_truth: Optional[set[str]],
    ) -> Optional[float]:
        if not ground_truth or not invoked_resources:
            return None
        unique = set(invoked_resources)
        redundant = len(unique - ground_truth)
        return round(redundant / len(unique), 4)

    def execute_view(
        self,
        view: VirtualView,
        ground_truth: Optional[set[str]] = None,
    ) -> ExecutionResult:
        """Simulate cross-node execution of a virtual view."""
        plan = self.create_task_plan(view)
        exec_plan = view.execution_plan or {}
        raw_tasks = exec_plan.get("tasks", [])
        execution_mode = plan.execution_mode
        node_groups = exec_plan.get("node_groups", {})

        local_results = [
            self.simulate_local_task(raw) for raw in raw_tasks
        ]
        merged = self.merge_results(local_results)

        invoked_nodes = merged["invoked_nodes"]
        invoked_resources = merged["invoked_resources"]
        latency_ms = self._compute_execution_latency(
            local_results, execution_mode, node_groups, merged["merge_latency_ms"]
        )

        redundant_ratio = self._redundant_invocation_ratio(invoked_resources, ground_truth)

        result_summary: dict[str, Any] = {
            "execution_mode": execution_mode,
            "invoked_node_count": len(invoked_nodes),
            "invoked_resource_count": len(invoked_resources),
            "merged_records": merged["merged_records"],
            "merge_latency_ms": merged["merge_latency_ms"],
            "task_count": len(local_results),
            "plan_id": plan.plan_id,
            "tasks": merged["task_results"],
        }
        if redundant_ratio is not None:
            result_summary["redundant_invocation_ratio"] = redundant_ratio
            result_summary["ground_truth_size"] = len(ground_truth)

        # Mark plan tasks completed
        for task in plan.tasks:
            task.status = TaskStatus.COMPLETED

        return ExecutionResult(
            view_id=view.view_id,
            demand_id=view.demand_id,
            invoked_nodes=invoked_nodes,
            invoked_resources=invoked_resources,
            result_summary=result_summary,
            latency_ms=latency_ms,
            status="completed" if local_results else "failed",
        )

    def execute_task_plan(
        self,
        plan: TaskPlan,
        ground_truth: Optional[set[str]] = None,
    ) -> ExecutionResult:
        """Execute from an existing TaskPlan (reconstructs minimal view context)."""
        raw_tasks = [
            {
                "task_id": t.task_id,
                "node_id": t.target_node_id,
                "resource_id": t.result.get("resource_id", ""),
                "operation": t.task_type,
                "params": t.result.get("params", {}),
            }
            for t in plan.tasks
        ]
        view = VirtualView(
            view_id=plan.view_id,
            demand_id=plan.demand_id,
            execution_plan={
                "tasks": raw_tasks,
                "execution_mode": plan.execution_mode,
                "node_groups": self._groups_from_tasks(raw_tasks),
            },
        )
        result = self.execute_view(view, ground_truth=ground_truth)
        plan.actual_duration_ms = result.latency_ms
        plan.efficiency_score = self._efficiency_score(plan, result)
        return result

    def _groups_from_tasks(self, raw_tasks: list[dict]) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for raw in raw_tasks:
            groups.setdefault(raw.get("node_id", ""), []).append(raw.get("task_id", ""))
        return groups

    def _efficiency_score(self, plan: TaskPlan, result: ExecutionResult) -> float:
        if plan.total_estimated_ms <= 0:
            return 1.0 if result.status == "completed" else 0.0
        ratio = result.latency_ms / plan.total_estimated_ms
        return round(max(0.5, min(1.0, 1.0 / max(ratio, 0.01))), 4)

    def parallel_execute_estimate(self, plan: TaskPlan) -> float:
        """Estimate wall-clock latency under parallel execution mode."""
        node_groups = self._groups_from_tasks(
            [
                {
                    "task_id": t.task_id,
                    "node_id": t.target_node_id,
                }
                for t in plan.tasks
            ]
        )
        return self._estimate_total_latency(plan.tasks, "parallel_by_node", node_groups)


class Orchestrator(TaskOrchestrator):
    """Backward-compatible orchestrator with demand-aware plan creation."""

    TASK_TYPES = [
        "metadata_discovery",
        "schema_alignment",
        "data_extraction",
        "view_materialization",
        "quality_validation",
        "delivery_notification",
    ]

    def create_plan(
        self,
        demand: DemandMetadata,
        view: VirtualView,
    ) -> TaskPlan:
        """Create orchestration plan from a virtual view (legacy API)."""
        plan = self.create_task_plan(view)
        plan.demand_id = demand.demand_id
        return plan

    def execute_plan(
        self,
        plan: TaskPlan,
        simulate: bool = True,
        ground_truth: Optional[set[str]] = None,
    ) -> TaskPlan:
        """Execute plan and update timing fields (legacy API)."""
        result = self.execute_task_plan(plan, ground_truth=ground_truth)
        plan.actual_duration_ms = result.latency_ms
        plan.efficiency_score = self._efficiency_score(plan, result)
        for task in plan.tasks:
            matching = next(
                (tr for tr in result.result_summary.get("tasks", []) if tr["task_id"] == task.task_id),
                None,
            )
            task.status = TaskStatus.COMPLETED if matching else TaskStatus.FAILED
            task.result = {
                "success": task.status == TaskStatus.COMPLETED,
                "duration_ms": matching["latency_ms"] if matching else 0,
                "node_id": task.target_node_id,
            }
        return plan
