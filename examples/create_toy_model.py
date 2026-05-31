"""Create a reproducible toy torch model artifact for Phase-1 CLI demos.

Usage:
  python3 examples/create_toy_model.py --out artifacts/toy_model.pt --in-features 16 --classes 3
"""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/toy_model.pt")
    parser.add_argument("--in-features", type=int, default=16)
    parser.add_argument("--classes", type=int, default=3)
    args = parser.parse_args()

    import torch
    import torch.nn as nn

    class TinyMLP(nn.Module):
        def __init__(self, in_features: int, num_classes: int):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(in_features, 32),
                nn.ReLU(),
                nn.Linear(32, num_classes),
            )

        def forward(self, x):
            return self.net(x)

    torch.manual_seed(42)
    model = TinyMLP(args.in_features, args.classes)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model, out_path)
    print(f"Saved toy model to: {out_path}")


if __name__ == "__main__":
    main()
