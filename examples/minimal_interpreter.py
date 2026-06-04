"""Minimal working interpreter example.

Demonstrates a custom interpretability method that computes
simple gradient-like attributions.

Run:
    python examples/minimal_interpreter.py
"""

from typing import Any, Dict, Optional
import random

from community_ai_audit.core.interfaces import InterpreterPlugin, InterpretationResult


class MinimalInterpreter(InterpreterPlugin):
    """Dummy interpreter that computes simple gradient-like attributions."""

    name = "minimal-demo"
    description = "Simple gradient-like attributions (demo interpreter)"
    version = "0.1.0"
    supported_model_types = []  # All types

    def interpret(
        self,
        model: Any,
        adapter: Any,
        inputs: Any,
        target: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> InterpretationResult:
        cfg = config or {}
        steps = cfg.get("steps", 10)

        print(f"[interpret] Running {self.name} with steps={steps}, target={target}")

        # Compute dummy attributions (in production, you'd compute real gradients)
        if isinstance(inputs, list):
            attributions = {
                "input": inputs,
                "scores": [abs(x * random.random()) for x in inputs],
                "top_feature": max(range(len(inputs)), key=lambda i: abs(inputs[i])),
            }
        else:
            attributions = {"input": str(inputs), "scores": [0.5]}

        # Sort features by importance
        if isinstance(inputs, list):
            attributions["feature_ranking"] = sorted(
                range(len(inputs)), key=lambda i: abs(inputs[i]), reverse=True
            )[:5]

        return InterpretationResult(
            interpreter_name=self.name,
            interpreter_version=self.version,
            attributions=attributions,
            summary=f"Top feature {attributions.get('top_feature', 'N/A')} most important across {steps} steps",
            metadata={"steps": steps, "target": target},
        )


if __name__ == "__main__":
    # Self-test without full engine
    from examples.minimal_adapter import DummyHTTPAdapter

    adapter = DummyHTTPAdapter()
    adapter.connect({"api_key": "test"})
    model = adapter.get_model("test-model")

    interpreter = MinimalInterpreter()
    result = interpreter.interpret(model, adapter, [0.5, -0.2, 0.8, 0.1])

    print(f"\nInterpreter: {result.interpreter_name}")
    print(f"Summary: {result.summary}")
    print(f"Attributions: {result.attributions}")
