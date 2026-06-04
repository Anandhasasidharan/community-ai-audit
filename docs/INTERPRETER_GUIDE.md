# Adding a New Interpreter — Step-by-Step

> **Time to complete:** ~30 minutes
> **Goal:** Add a new interpretability method to explain model predictions.

## 1. Understand the Interface

An interpreter implements `InterpreterPlugin` which requires:

| Method | Purpose |
|--------|---------|
| `interpret(model, adapter, inputs, target, config)` | Run attribution, return `InterpretationResult` |

Your interpreter receives:
- `model`: The loaded model
- `adapter`: The `ModelAdapter` (for `predict()`, `tokenize()`, etc.)
- `inputs`: The input data to explain
- `target`: Optional target class/token to attribute
- `config`: Dict with configuration (e.g., `steps`, `baseline`)

Your interpreter returns:
- `InterpretationResult` — attributions, summary, optional visualizations

## 2. Create Your Interpreter File

Create `community_ai_audit/plugins/interpreters/my_interpreter.py`:

```python
"""My custom interpretability method."""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import InterpreterPlugin, InterpretationResult

log = logging.getLogger(__name__)

class MyInterpreter(InterpreterPlugin):
    name = "my-interpreter"
    description = "Custom attributions using XYZ method"
    version = "0.1.0"
    supported_model_types = []  # Empty = all types

    def interpret(
        self,
        model: Any,
        adapter: Any,
        inputs: Any,
        target: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> InterpretationResult:
        cfg = config or {}
        num_baseline_samples = cfg.get("num_baseline", 10)

        # --- Your attribution logic here ---
        # Example: compute simple gradient-based attribution
        # predictions = adapter.predict(model, inputs)
        # attributions = compute_attributions(predictions, target)
        # -------------------------------------

        # Dummy implementation
        attributions = {"input": inputs, "score": 0.5}

        return InterpretationResult(
            interpreter_name=self.name,
            interpreter_version=self.version,
            attributions=attributions,
            summary=f"Attribution computed with {num_baseline_samples} baseline samples",
            metadata={"num_baseline": num_baseline_samples},
        )
```

## 3. Test Your Interpreter

```python
from community_ai_audit.plugins.interpreters.my_interpreter import MyInterpreter

interp = MyInterpreter()
# model and adapter from AuditEngine.load_model(...)
result = interp.interpret(model, adapter, [0.1, 0.2, 0.3])
print(result.attributions)
```

## 4. Run via CLI

```bash
community-ai-audit interpret model.pt --provider local --interpreters my-interpreter --input '[0.1,0.2,0.3]'
```

## Key Patterns

- **Baseline selection**: Support `zero`, `random`, `blur`, or learned baselines
- **Target**: Allow specifying which output class/token to attribute
- **Visualization**: Return structured data that reporters can plot
- **Batching**: Process multiple samples when possible for efficiency

## Full Working Example

See `examples/minimal_interpreter.py` for a complete minimal interpreter.
