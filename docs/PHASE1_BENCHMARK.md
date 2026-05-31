# Phase 1 Reproducible Benchmark (Toy Local Model)

This benchmark verifies the Phase-1 working path:
- local model loading
- adversarial scanner
- integrated-gradients interpreter

## 1) Create toy model artifact

```bash
python3 examples/create_toy_model.py --out artifacts/toy_model.pt --in-features 16 --classes 3
```

## 2) Run discovery

```bash
community-ai-audit discover
```

## 3) Run adversarial scan

```bash
community-ai-audit scan artifacts/toy_model.pt \
  --provider local \
  --scanners adversarial \
  --probe-file examples/data/toy_probe.json \
  --output markdown
```

(You can also use synthetic probes with `--input-shape '[16]'`.)

## 4) Run integrated gradients

```bash
community-ai-audit interpret artifacts/toy_model.pt \
  --provider local \
  --interpreters integrated-gradients \
  --input '[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]' \
  --output markdown
```

## 5) Run full audit

```bash
community-ai-audit audit artifacts/toy_model.pt \
  --provider local \
  --profile standard \
  --scanners adversarial backdoor \
  --interpreters integrated-gradients \
  --probe-file examples/data/toy_probe.json \
  --input '[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]' \
  --output markdown
```

## 6) Save benchmark artifacts (recommended)

```bash
python3 examples/run_phase1_benchmark.py \
  --model artifacts/toy_model.pt \
  --probe-file examples/data/toy_probe.json \
  --profile standard \
  --out-dir reports/phase1
```

This writes timestamped markdown + JSON reports to `reports/phase1/`.

## Notes
- Requires `torch` installed.
- Backdoor scanner uses synthetic probes unless `probe_inputs` are provided.
- Results are for pipeline verification, not security ground-truth accuracy.
