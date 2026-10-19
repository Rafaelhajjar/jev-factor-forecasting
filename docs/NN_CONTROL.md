# Can the appendix NN match its unemployment forecast cell?

Declared October 19, 2026, after the earlier primary, sensitivity and conventional-control results, but **before this NN control's actual-data pilot or full outcomes**. The [configuration](../configs/mrf_nn.json) freezes both the paper-supported architecture and our explicit choices where the original runner is missing. It does not replace the still-failed primary FA-ARRF result.

## Problem, inputs, target

Main Table 2 of [Goulet Coulombe (2024)](https://doi.org/10.1002/jae.3030), PDF page 9, defines NN as a direct nonlinear forecast from the entire rich state S(t). Use the original **1,041 state columns**, not just two factors or the small MRF equation. This is the plain feed-forward NN, not the separate macro neural network (MNN) with coefficient-specific outputs.

Keep the original all-248 preparation, all matrix entries/masks, delta-log unemployment, 48 target dates in 2003Q1–2014Q4 and six expanding two-year refits. Each declared seed has a 10-member ensemble at each refit. Seeds 101/202/303 therefore give 18 ensemble fits and **180 neural networks**, each with a 100-epoch cap. The fitting window contains only outcomes known before that block's first forecast. Future target placeholders are never passed to training.

The appendix's Table 4 reports NN/AR(4) = **0.80** for unemployment h=1. Keep the original AR(4) denominator and the unchanged absolute-ratio tolerance of 0.03. Require all three individual seed ensembles to pass. A separately labeled mean across the three seed ensembles cannot rescue a miss. These are our diagnostic rules, not author standards or statistical tests; source significance stars do not transfer.

## What does the source actually specify?

Appendix A.2, PDF pages 11-12 (printed 50-51), specifies an average of 10 fits, 85% subsampling with the remaining 15% used for validation, batch size 32, Adam with Torch defaults, learning rate 0.001, up to 100 epochs and early stopping. The plain NN has five fully connected 100-unit hidden layers, ReLU activations and a linear output. Continuous inputs are standardized. Main Table 2 points to this appendix for the real-data architecture.

The article's 2020b reference is **To Bag Is to Prune**, [arXiv:2008.07063](https://arxiv.org/abs/2008.07063), not an independently recovered NN implementation. The inspected bagofprunes package at commit 3c45cb91d32de51ba63135c4f549a2d055a377cc contains Booging/MARSquake helpers, not the original MRF NN benchmark runner. The later hemisphere archive inventory and HNN function interface describe a different grouped neural model. They do not verify the 2024 NN table's training invocation. We do not import that later model's target scaling or hyperparameters.

Original patience/tolerance, checkpoint restoration, scaling details, exact sampling/RNG convention and runtime remain unknown. Our trainer is an independent, explicitly qualified reconstruction, not execution of an obtained original NN script.

## Which missing choices are fixed now?

| Item | This reconstruction |
| --- | --- |
| Feature scaling | Fitting-window means and sample SDs, shared by the 10 members; SD at or below 1e-12 uses unit scale |
| Target | Raw delta-log target, with no additional target scaling; the source explicitly specifies X standardization but does not settle Y scaling |
| Subsample | floor(0.85 × fitting rows), without replacement; sorted row identities, with the complement retained for validation |
| Initialization and batching | Pinned Torch Linear defaults; separate deterministic partition/initialization/batch streams; reshuffle fitting rows each epoch, retaining the final short batch |
| Optimization | Mean squared error; Adam betas 0.9/0.999, epsilon 1e-8, zero weight decay, no AMSGrad/dropout; non-fused/non-foreach CPU execution |
| Early stopping | Patience 10, strict improvement with min_delta 0, first eligible checkpoint after epoch one, restore the lowest validation-MSE checkpoint |
| Execution | PyTorch 2.14.1, float32 CPU, one thread and deterministic algorithms; no GPU or compilation |

These choices are fixed before new NN forecast losses. They are not facts recovered about the missing caller. [Versioned Linear documentation](https://docs.pytorch.org/docs/2.14/generated/torch.nn.Linear.html) and [Adam documentation](https://docs.pytorch.org/docs/2.14/generated/torch.optim.Adam.html) establish the modern backend semantics. We do not claim historical Torch/R RNG equivalence or cross-platform bitwise identity.

Scaling includes validation **covariates** from the past fitting window, but does not directly use validation target values for moments. Features such as target lags and PCA are already constructed on that window; this random holdout is not a chronological or genuinely prequential assessment. It is the source-inspired reconstruction track. Our later policy development still requires chronological/prequential validation and timestamped information.

Training and validation see no forecast target. Nonfinite loss, gradient, parameters or forecasts fail the fit; there is no fallback, seed search or silent replacement. Average member **forecasts**, not network parameters. Retain all members, all three seed ensembles and the separately labeled outer-seed mean. The 10-member source-style ensemble and the extra three-seed robustness exercise are different levels of averaging.

## Verification before interpretation

Repeat the entire original primary audit, including reconstruction of all six state matrices and independent R linear checks. Bind matrices/settings, origin/target grid, complete primary configuration, declaration, source files, PyTorch build/backend and dependency lock. Resume rejects changed inputs/code/runtime. Completed checkpoints are verified rather than retrained silently; incomplete member directories are preserved rather than overwritten.

Each member saves only data: compressed numeric parameter arrays and JSON splits, RNG streams, scaling, epoch losses, batch-order hashes, selected checkpoint and forecasts. No pickle loading is needed. Independent NumPy traversal and MSE calculations check the restored model. Actual-Torch contracts check initialization/topology, derivatives and Adam updates against independent calculations; controlled tests verify early stopping/restoration and reject a valid-looking substitute model.

The final auditor **repeats all 180 declared trainings** and requires identical parameters, splits, epoch histories, stopping decisions and forecasts on the recorded platform. It also rebuilds ensemble/member forecasts, dates, aggregates, metrics and the diagnostic. Arithmetic checks allow absolute 2e-6 plus relative 2e-5 for float32 Torch/NumPy differences; full-training replay is exact.

A pilot uses one member, two epochs, seed 101 and one refit/eight dates. It reports integrity only. Reduced, preparation-only and incomplete runs suppress performance scores. Full scores require the unchanged 10-member, 100-epoch-cap, three-seed declaration and all six refits.

## Reproduce

Run from the repository checkout after the complete original primary run. The NN dependency is optional and [configured for CPU wheels](https://docs.astral.sh/uv/guides/integration/pytorch/), without altering the existing core package versions.

~~~bash
uv sync --frozen --extra nn
uv run --frozen --extra nn python scripts/nn_control.py run \
  --source-run runs/mrf-unemployment --output runs/nn-pilot \
  --members 1 --epochs 2 --seeds 101 --max-refits 1
uv run --frozen --extra nn python scripts/nn_control.py audit \
  --run runs/nn-pilot --output reports/my-nn-pilot.json --allow-partial

uv run --frozen --extra nn python scripts/nn_control.py run \
  --source-run runs/mrf-unemployment --output runs/nn-full
uv run --frozen --extra nn python scripts/nn_control.py audit \
  --run runs/nn-full --output reports/my-nn-full-audit.json
~~~

Use --prepare-only for a declaration/input record with no training or scores, and --resume for an unchanged run. All 423 local tests passed at declaration: 345 base, 53 optional NN and 25 optional real-R contracts. CI runs the actual NN training/refit on a clearly synthetic source boundary, not the full macro experiment. No Jev, LLM, hosted forecasting or paid API calls occur. All earlier results and the open FA-ARRF requirement remain preserved.
