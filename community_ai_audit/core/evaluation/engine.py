from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from community_ai_audit.core.audit import AuditEngine
from community_ai_audit.core.scoring.engine import ScoringEngine

from .models import EvaluationResult, BenchmarkResult, RegressionReport

log = logging.getLogger(__name__)


class EvaluationEngine:
    """Orchestrates model evaluation, benchmarking, and regression testing.

    Wraps AuditEngine and adds:
    - evaluate(): run scanners + policies + reliability checks + risk scoring
    - benchmark(): run a model against a benchmark dataset
    - regression(): compare two benchmark runs for regression detection
    """

    def __init__(
        self,
        audit_engine: Optional[AuditEngine] = None,
        scoring_engine: Optional[ScoringEngine] = None,
        config_path: Optional[str] = None,
    ):
        self.audit = audit_engine or AuditEngine(config_path=config_path)
        self.scoring = scoring_engine or ScoringEngine()
        self._session_id: str = ""

    # ── Evaluate ──────────────────────────────────────────────

    def evaluate(
        self,
        model_id: str,
        provider: str,
        adapter_config: Optional[Dict[str, Any]] = None,
        scanners: Optional[List[str]] = None,
        policies: Optional[List[str]] = None,
        reliability_checks: Optional[List[str]] = None,
        agent_scanners: Optional[List[str]] = None,
        agent_session: Optional[Any] = None,
        policy_config: Optional[Dict[str, Any]] = None,
        scoring_weights: Optional[Dict[str, float]] = None,
        probe_inputs: Optional[List[Any]] = None,
        **model_kwargs,
    ) -> EvaluationResult:
        """Run a full evaluation: scan + policy check + reliability + agent audit + scoring.

        Args:
            model_id: Model identifier.
            provider: Model provider name.
            adapter_config: Optional adapter config.
            scanners: Scanner names to run. None = all.
            policies: Policy names to check. None = all.
            reliability_checks: Reliability scanner names. None = none.
            agent_scanners: Agent scanner names to run. None = none.
            agent_session: AgentAuditSession for agent risk evaluation.
            policy_config: Config passed to policy plugins.
            scoring_weights: Custom scoring dimension weights.
            probe_inputs: Optional probe inputs for scanners.
            **model_kwargs: Additional args for load_model.

        Returns:
            EvaluationResult with all findings, policy results, and risk scores.
        """
        started_at = datetime.now(timezone.utc)
        self._session_id = f"eval-{int(time.time())}"
        result = EvaluationResult(
            model_id=model_id,
            adapter_name=provider,
            started_at=started_at,
            session_id=self._session_id,
        )

        if scoring_weights:
            self.scoring = ScoringEngine(weights=scoring_weights)

        try:
            self.audit.load_model(
                model_id, provider=provider, adapter_config=adapter_config, **model_kwargs
            )
        except Exception as e:
            log.error("Failed to load model '%s': %s", model_id, e)
            result.completed_at = datetime.now(timezone.utc)
            result.duration_seconds = (result.completed_at - started_at).total_seconds()
            result.risk_scores = self.scoring.compute().to_dict()
            return result

        # 1. Run scanners
        if scanners is not None or probe_inputs:
            try:
                if probe_inputs:
                    sr = self.audit.scan(scanners=scanners)
                else:
                    sr = self.audit.scan(scanners=scanners)
                result.scan_results = [r.to_dict() for r in sr]
            except Exception as e:
                log.error("Scan failed: %s", e)

        # 2. Run policy checks
        if policies:
            result.policy_results = self._run_policies(policies, policy_config)

        # 3. Run reliability checks
        if reliability_checks:
            result.reliability_results = self._run_reliability_checks(reliability_checks)

        # 4. Run agent scanners
        agent_results = []
        if agent_scanners and agent_session:
            try:
                agent_results = self._run_agent_scanners(agent_scanners, agent_session)
            except Exception as e:
                log.error("Agent audit failed: %s", e)

        # 5. Compute risk scores
        try:
            risk = self.scoring.compute(
                scan_results=result.scan_results,
                policy_results=result.policy_results,
                reliability_results=result.reliability_results,
                agent_results=agent_results,
            )
            result.risk_scores = risk.to_dict()
        except Exception as e:
            log.error("Scoring failed: %s", e)

        result.completed_at = datetime.now(timezone.utc)
        result.duration_seconds = (result.completed_at - started_at).total_seconds()
        return result

    # ── Benchmark ─────────────────────────────────────────────

    def benchmark(
        self,
        model_id: str,
        provider: str,
        dataset_name: str,
        dataset_version: str = "latest",
        adapter_config: Optional[Dict[str, Any]] = None,
        sample_limit: Optional[int] = None,
        batch_size: int = 1,
        **model_kwargs,
    ) -> BenchmarkResult:
        """Run a model against a benchmark dataset.

        Args:
            model_id: Model identifier.
            provider: Model provider name.
            dataset_name: Name of the dataset to benchmark against.
            dataset_version: Dataset version string.
            adapter_config: Optional adapter config.
            sample_limit: Limit number of samples to evaluate.
            batch_size: Batch size for processing.
            **model_kwargs: Additional args for load_model.

        Returns:
            BenchmarkResult with pass/fail stats and per-sample results.
        """
        started_at = datetime.now(timezone.utc)
        dataset = self._load_dataset(dataset_name, dataset_version)
        if dataset is None:
            raise ValueError(f"Dataset '{dataset_name}' (v{dataset_version}) not found.")

        samples = dataset.get("samples", [])
        if not samples:
            raise ValueError(f"Dataset '{dataset_name}' has no samples.")

        if sample_limit and sample_limit < len(samples):
            samples = samples[:sample_limit]

        try:
            self.audit.load_model(
                model_id, provider=provider, adapter_config=adapter_config, **model_kwargs
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load model '{model_id}': {e}") from e

        num_passed = 0
        num_failed = 0
        per_sample = []
        scores: Dict[str, float] = {}
        passed_list = []

        for i, sample in enumerate(samples):
            prompt = sample.get("prompt", sample.get("input", ""))
            expected = sample.get("expected", sample.get("label", ""))
            category = sample.get("category", "general")

            try:
                output = self.audit._adapter.generate(self.audit._model, prompt)
                passed = self._check_expected(output, expected)
                if passed:
                    num_passed += 1
                else:
                    num_failed += 1
                passed_list.append(passed)

                per_sample.append(
                    {
                        "index": i,
                        "category": category,
                        "prompt_preview": prompt[:120] + ("..." if len(prompt) > 120 else ""),
                        "expected": expected[:200] if expected else "",
                        "output_preview": output[:200] if output else "",
                        "passed": passed,
                    }
                )

                log.debug(
                    "Benchmark sample %d/%d: %s", i + 1, len(samples), "PASS" if passed else "FAIL"
                )

            except Exception as e:
                num_failed += 1
                passed_list.append(False)
                per_sample.append(
                    {
                        "index": i,
                        "category": category,
                        "prompt_preview": prompt[:120],
                        "error": str(e),
                        "passed": False,
                    }
                )

        accuracy = num_passed / len(samples) if samples else 0.0
        scores["accuracy"] = accuracy

        completed_at = datetime.now(timezone.utc)
        return BenchmarkResult(
            benchmark_name=f"{dataset_name}-benchmark",
            dataset_name=dataset_name,
            dataset_version=dataset.get("version", dataset_version),
            model_id=model_id,
            adapter_name=provider,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(completed_at - started_at).total_seconds(),
            num_samples=len(samples),
            num_passed=num_passed,
            num_failed=num_failed,
            accuracy=accuracy,
            scores=scores,
            per_sample_results=per_sample,
            metrics={
                "sample_limit": sample_limit,
                "batch_size": batch_size,
                "categories": list(set(s.get("category", "general") for s in samples)),
            },
        )

    # ── Regression ────────────────────────────────────────────

    def regression(
        self,
        baseline: BenchmarkResult,
        current: BenchmarkResult,
        threshold: float = 0.05,
    ) -> RegressionReport:
        """Compare two benchmark runs and detect regression.

        Args:
            baseline: Earlier benchmark result.
            current: Later benchmark result.
            threshold: Minimum delta to flag as regression/improvement (default 0.05 = 5%).

        Returns:
            RegressionReport with deltas, regressions, and improvements.
        """
        if baseline.benchmark_name != current.benchmark_name:
            raise ValueError(
                f"Cannot compare different benchmarks: '{baseline.benchmark_name}' vs '{current.benchmark_name}'"
            )

        if baseline.model_id != current.model_id:
            log.warning(
                "Comparing different models: '%s' vs '%s'",
                baseline.model_id,
                current.model_id,
            )

        metric_deltas: Dict[str, float] = {}
        regressions: List[str] = []
        improvements: List[str] = []

        all_metrics = set(baseline.scores.keys()) | set(current.scores.keys())
        for metric in sorted(all_metrics):
            base_val = baseline.scores.get(metric, 0.0)
            curr_val = current.scores.get(metric, 0.0)
            delta = curr_val - base_val
            metric_deltas[metric] = round(delta, 4)

            if abs(delta) >= threshold:
                if delta < 0:
                    regressions.append(f"{metric}: {base_val:.3f} -> {curr_val:.3f} ({delta:+.3f})")
                else:
                    improvements.append(
                        f"{metric}: {base_val:.3f} -> {curr_val:.3f} ({delta:+.3f})"
                    )

        return RegressionReport(
            baseline=baseline,
            current=current,
            metric_deltas=metric_deltas,
            regressions=regressions,
            improvements=improvements,
            threshold=threshold,
        )

    # ── Internal helpers ──────────────────────────────────────

    def _run_policies(
        self, policies: List[str], config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        from community_ai_audit.plugins.policies import run_policies

        return run_policies(
            policies=policies,
            model=self.audit._model,
            adapter=self.audit._adapter,
            config=config,
        )

    def _run_agent_scanners(
        self, scanners: List[str], session: Any
    ) -> List[Dict[str, Any]]:
        from community_ai_audit.plugins.agents import run_agent_scanners

        return run_agent_scanners(
            scanners=scanners,
            session=session,
        )

    def _run_reliability_checks(self, checks: List[str]) -> List[Dict[str, Any]]:
        from community_ai_audit.plugins.reliability import run_reliability_checks

        return run_reliability_checks(
            checks=checks,
            model=self.audit._model,
            adapter=self.audit._adapter,
        )

    def _load_dataset(self, name: str, version: str = "latest") -> Optional[Dict[str, Any]]:
        """Load a dataset by name and version."""
        from community_ai_audit.datasets.registry import get_dataset

        return get_dataset(name, version)

    def _check_expected(self, output: str, expected: str) -> bool:
        """Check if model output matches expected result.

        Supports exact match, substring match, and simple patterns.
        """
        if not expected:
            return True
        if expected.startswith("not:"):
            return expected[4:].strip().lower() not in output.lower()
        if expected.startswith("re:"):
            import re

            try:
                return bool(re.search(expected[3:].strip(), output))
            except re.error:
                return expected.lower() in output.lower()
        return expected.lower() in output.lower()
