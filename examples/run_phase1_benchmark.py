"""Run a reproducible Phase-1 benchmark and save report artifacts.

Usage:
  python3 examples/run_phase1_benchmark.py \
    --model artifacts/toy_model.pt \
    --probe-file examples/data/toy_probe.json \
    --out-dir reports/phase1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Allow running this script directly from source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from community_ai_audit import AuditEngine, ReportGenerator  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="artifacts/toy_model.pt")
    parser.add_argument("--provider", default="local")
    parser.add_argument("--probe-file", default="examples/data/toy_probe.json")
    parser.add_argument("--profile", default="standard", choices=["quick", "standard", "deep"])
    parser.add_argument("--out-dir", default="reports/phase1")
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model file not found: {model_path}. "
            f"Create one with: python3 examples/create_toy_model.py --out {model_path}"
        )

    probe_path = Path(args.probe_file)
    if not probe_path.exists():
        raise FileNotFoundError(f"Probe file not found: {probe_path}")

    with probe_path.open("r", encoding="utf-8") as f:
        probe_inputs = json.load(f)

    if not isinstance(probe_inputs, list) or not probe_inputs:
        raise ValueError("Probe file must contain a non-empty JSON list")

    # Profile defaults
    if args.profile == "quick":
        adv_cfg = {"num_samples": 16, "pgd_steps": 5}
        bd_cfg = {"sample_size": 64, "max_layers": 8}
        ig_cfg = {"steps": 30}
    elif args.profile == "deep":
        adv_cfg = {"num_samples": 128, "pgd_steps": 20}
        bd_cfg = {"sample_size": 512, "max_layers": 32}
        ig_cfg = {"steps": 100}
    else:
        adv_cfg = {"num_samples": 32, "pgd_steps": 10}
        bd_cfg = {"sample_size": 128, "max_layers": 16}
        ig_cfg = {"steps": 50}

    scanner_overrides = {
        "adversarial": {**adv_cfg, "probe_inputs": probe_inputs},
        "backdoor": {**bd_cfg, "probe_inputs": probe_inputs},
        "integrated-gradients": ig_cfg,
    }

    run_metadata = {
        "profile": args.profile,
        "provider": args.provider,
        "probe_source": str(probe_path),
        "probe_count": len(probe_inputs),
    }

    engine = AuditEngine(discovery_on_init=True)
    engine.load_model(str(model_path), provider=args.provider, adapter_config={"device": "cpu"})

    session = engine.audit(
        scanners=["adversarial", "backdoor"],
        interpreters=["integrated-gradients"],
        inputs=probe_inputs[0],
        connectors=None,
        config_overrides=scanner_overrides,
        run_metadata=run_metadata,
    )

    reporter = ReportGenerator()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"{stamp}_phase1_audit.md"
    json_path = out_dir / f"{stamp}_phase1_audit.json"

    md_text = reporter.render_session(session, fmt="markdown")
    json_text = reporter.render_session(session, fmt="json")

    md_path.write_text(md_text, encoding="utf-8")
    json_path.write_text(json_text, encoding="utf-8")

    print(f"Saved markdown report: {md_path}")
    print(f"Saved JSON report: {json_path}")
    print(session.summary())


if __name__ == "__main__":
    main()
