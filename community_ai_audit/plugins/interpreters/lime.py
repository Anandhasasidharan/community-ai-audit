"""
LIME (Local Interpretable Model-agnostic Explanations) interpreter.
Generates locally faithful explanations by perturbing inputs and fitting
sparse linear models.

Works with any ModelAdapter since it only requires predict() via the adapter.
No gradients needed — fully black-box compatible.
"""

import logging
from typing import Any, Dict, Optional, List

from community_ai_audit.core.interfaces import (
    InterpreterPlugin,
    InterpretationResult,
    ModelAdapter,
)

log = logging.getLogger(__name__)


def safe_import(name, package=None):
    import importlib

    try:
        return importlib.import_module(name, package=package)
    except ImportError:
        return None


class LIMEInterpreter(InterpreterPlugin):
    """Interpreter using LIME for local model-agnostic explanations.

    Perturbs input features, observes model prediction changes, and fits
    a sparse interpretable model around the local neighborhood.
    Ideal for black-box API models where gradients are unavailable.

    Config keys:
        num_samples (int): Number of perturbation samples. Default: 1000.
        kernel_width (float): Width of exponential kernel for locality.
            Default: 0.75.
        feature_selection (str): 'auto' or 'forward_selection', etc.
            Default: 'auto'.
        top_features (int): Number of top features to explain. Default: 10.
    """

    name = "lime"
    description = "Local interpretable model-agnostic explanations"
    version = "0.1.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._num_samples = self.config.get("num_samples", 1000)
        self._kernel_width = self.config.get("kernel_width", 0.75)
        self._top_features = self.config.get("top_features", 10)
        self._feature_selection = self.config.get("feature_selection", "auto")

    def interpret(
        self,
        model: Any,
        adapter: ModelAdapter,
        inputs: Any,
        target: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> InterpretationResult:
        """Generate LIME explanations for given inputs.

        Args:
            model: The loaded model.
            adapter: The ModelAdapter for inference (must provide predict()).
            inputs: Input sample(s) to explain.
            target: Optional target class, token position, etc.
            config: Optional runtime overrides.

        Returns:
            InterpretationResult with feature importances.
        """
        if config:
            self.config = {**self.config, **config}

        # Check if model is a text/language model
        is_text_model = (
            hasattr(model.config, "vocab_size")
            or hasattr(model, "vocab_size")
            or hasattr(model, "wte")  # GPT-2 style
        )

        if not is_text_model:
            return InterpretationResult(
                interpreter_name=self.name,
                interpreter_version=self.version,
                error="LIME text explainer only supports text models. For image/tabular models, use lime_image or lime_tabular.",
            )

        # Check adapter has tokenize — required for LIME text perturbations
        if not hasattr(adapter, "tokenize"):
            return InterpretationResult(
                interpreter_name=self.name,
                interpreter_version=self.version,
                error="This adapter does not support tokenization required by LIME. Use a TextModelAdapter (e.g. huggingface, local).",
            )

        # Try importing LIME, fall back if not available
        lime = safe_import("lime.lime_text")
        if lime is None:
            return InterpretationResult(
                interpreter_name=self.name,
                interpreter_version=self.version,
                error="LIME library not installed. Run: pip install lime",
            )

        try:
            return self._explain_text(model, adapter, inputs, target)

        except Exception as e:
            log.exception("LIME failed")
            return InterpretationResult(
                interpreter_name=self.name,
                interpreter_version=self.version,
                error=f"{type(e).__name__}: {e}",
            )

    def _explain_text(
        self, model: Any, adapter: ModelAdapter, text_input: str, target: Optional[Any]
    ) -> InterpretationResult:
        from lime import lime_text
        import numpy as np

        class _Predictor:
            def __init__(self, _model, _adapter, _target):
                self.model = _model
                self.adapter = _adapter
                self.target = _target

            def predict(self, texts: List[str]) -> np.ndarray:
                probs = []
                for t in texts:
                    output = self.adapter.predict(self.model, self.adapter.tokenize(t))
                    if hasattr(output, "logits"):
                        logits = output.logits.detach().cpu().numpy()
                        prob = np.exp(logits) / np.sum(np.exp(logits), axis=-1, keepdims=True)
                        probs.append(prob)
                    else:
                        probs.append(np.zeros(1))
                return np.vstack(probs)

        explainer = lime_text.LimeTextExplainer(
            class_names=["prediction"],
            feature_selection=self._feature_selection,
        )
        predictor = _Predictor(model, adapter, target)

        explanation = explainer.explain_instance(
            text_input if isinstance(text_input, str) else str(text_input),
            predictor.predict,
            num_features=self._top_features,
            num_samples=min(self._num_samples, 500),
        )

        feature_importances = dict(explanation.as_list())

        return InterpretationResult(
            interpreter_name=self.name,
            interpreter_version=self.version,
            attributions={"lime": feature_importances},
            summary=(
                f"Top feature: {max(feature_importances, key=feature_importances.get)} ({max(feature_importances.values()):.3f})"
                if feature_importances
                else "No feature importances found."
            ),
            metadata={
                "num_samples": self._num_samples,
                "kernel_width": self._kernel_width,
                "top_features": self._top_features,
            },
        )
