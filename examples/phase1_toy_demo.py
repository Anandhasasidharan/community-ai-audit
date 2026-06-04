"""Phase 1 demo: run scanner + interpreter end-to-end on a toy local torch model.

Usage:
  python3 examples/phase1_toy_demo.py
"""

from pathlib import Path
import tempfile
import sys

import torch
import torch.nn as nn

# Allow running this script directly from source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from community_ai_audit import AuditEngine  # noqa: E402


class TinyMLP(nn.Module):
    def __init__(self, in_features: int = 16, num_classes: int = 3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, 32),
            nn.ReLU(),
            nn.Linear(32, num_classes),
        )

    def forward(self, x):
        return self.net(x)


def main():
    # 1) Build + save a toy model file that LocalAdapter can load
    model = TinyMLP()
    tmp_dir = Path(tempfile.gettempdir())
    model_path = tmp_dir / "community_ai_audit_toy_model.pt"
    torch.save(model, model_path)

    # 2) Create engine and load model through local adapter
    engine = AuditEngine(discovery_on_init=True)
    engine.load_model(str(model_path), provider="local", adapter_config={"device": "cpu"})

    # 3) Run adversarial scanner with synthetic probe shape
    scan_results = engine.scan(
        scanners=["adversarial"],
        config_overrides={"adversarial": {"input_shape": [16], "num_samples": 32, "epsilon": 0.1}},
    )

    # 4) Run integrated gradients on one sample
    sample = [0.1] * 16
    interpret_results = engine.interpret(
        inputs=sample,
        interpreters=["integrated-gradients"],
    )

    # 5) Print outputs
    print("\n=== Scan Results ===")
    for r in scan_results:
        print(r.to_dict())

    print("\n=== Interpret Results ===")
    for r in interpret_results:
        print(r.to_dict())


if __name__ == "__main__":
    main()
