# Does the native normalization helper explain the FA-ARRF gap?

Declared October 19, 2026, **before this diagnostic's actual-data pilot or full forecasts**. Earlier primary/comparator losses and the twelve [initialization probes](NATIVE_NORMALIZATION_BOUNDARY.md) are already known. This is a source-backed interface diagnostic, not a blind test, a search for a favorable setting, or a replacement primary.

## Problem, inputs, target

The pinned author's engine uses all supplied rows for its inner normalization. Our first reconstruction deliberately uses training-only moments. The source probe establishes that switching helpers changes both normalization and the implemented OLS-prior intercept conversion. It does not establish the forecast effect. This experiment measures that specific difference with the native conversion left untouched.

Use the original all-248 preparation and exact original 1,041-column state matrices, delta-log unemployment h=1, six expanding two-year refits and 48 target dates in 2003Q1–2014Q4. Keep all three seeds (101/202/303), 100 trees, block parameter 8, sampling, ridge/RWR/MLF, priors, basis orientation and effective parent-size guard. Do not stack R signs, PCA125 or FRED125. Every fixed-factor and AR forecast must be exactly unchanged.

The [configuration](../configs/mrf_native_allrows.json) differs from the primary only in `standardization` and the corresponding assumption label. The small equation still has an intercept, two target lags and two factors; the rich state is unchanged. All source/caller uncertainties except this helper selection remain unresolved.

## What changes, and what does not?

The existing adapter still masks every future target and applies outer **training-only** centering/scaling. The engine then runs its literal native all-supplied-row helper, rather than our helper override. Keep the native prior conversion, including the documented intercept interaction. Do not fix it at the same time. This is the native-helper path behind the same adapter, not an obtained original table caller or an assertion about how the author passed raw data.

The native inner moments use covariates from later origins within the eight-quarter forecast block. Those values need not be available at the first origin. Therefore this is **not a causal forecast comparison** or a deployable alternative baseline. Future outcomes remain masked, but masking outcomes does not make use of future covariates causal. A numerical match cannot resolve the missing original caller or justify using this mode for Jev policy training.

## What is fixed before new outcomes?

- All 18 original refit/seed cases must finish. Retain every seed and a separately labeled mean-prediction ensemble; no best-seed selection.
- Keep the original AR(4) denominator and matching fixed FA-AR comparator. The diagnostic requires FA-AR within 0.03 of 0.83 and **each** forest seed within 0.03 of 0.72. The mean ensemble cannot rescue a miss. These are project diagnostics, not author standards or statistical tests.
- Report each forest's incremental RMSE reduction against its own matching FA-AR. Merely matching a rounded cell does not establish the larger source nonlinear gain.
- First run a two-tree, one-seed, one-refit/eight-date pilot. Its public audit and terminal summary withhold performance. The legacy underlying runner may retain private reduced-run metric files; those are not used for tuning, interpreted as full results or published as benchmark evidence.
- No retry with altered settings, corrected source, new seeds or different factors based on the diagnostic loss. A source/code defect requires a fresh declaration and output directory, preserving the previous artifacts.

## Verification

The [paired wrapper](../src/jev_factor/native_allrows.py) repeats the complete original primary audit. Before any forest is launched, it requires exact matrix SHA equality, identical representation metadata and target/origin records, identical linear forecasts, and settings changed only by the helper mode (plus explicitly reduced pilot tree counts). Pinned engine and adapter/preparation source hashes must be unchanged. It binds the declaration, source manifest/predictions and verification code for resume.

The final audit independently reconstructs state inputs from the archive, checks all coefficient decompositions in original units, compares linear calculations with base-R QR, recomputes all forecast aggregates/metrics and verifies R/pracma version equality with the primary. These are the existing actual-engine artifact checks, not a claim of refitting every tree or recovering the unknown table pipeline. Reduced/incomplete runs receive no published forest score or numerical pass. The original primary remains immutable.

Twenty-five new synthetic-boundary contracts cover configuration changes, actual input/setting/target/grid/metadata mutations, preparation-before-fitting, altered source provenance, runtime drift and score suppression even if a mocked upstream completion flag incorrectly says full. Separate existing actual-R contracts establish future-target masking and the native mode's dependence on later forecast-row covariates; the twelve actual initialization probes verify the normalization/prior interaction. None of those synthetic or initialization checks is a macro forecast result.

## Run

Run from the repository checkout, after the full original primary reconstruction:

~~~bash
uv run --frozen python scripts/native_allrows_diagnostic.py run \
  --source-run runs/mrf-unemployment --output runs/native-helper-pilot \
  --trees 2 --seeds 101 --max-refits 1
uv run --frozen python scripts/native_allrows_diagnostic.py audit \
  --run runs/native-helper-pilot --output reports/my-native-helper-pilot.json --allow-partial

uv run --frozen python scripts/native_allrows_diagnostic.py run \
  --source-run runs/mrf-unemployment --output runs/native-helper-full --workers 4
uv run --frozen python scripts/native_allrows_diagnostic.py audit \
  --run runs/native-helper-full --output reports/my-native-helper-full.json
~~~

Use `--prepare-only` to verify inputs without fitting; resume with `--resume` and the exact original pilot/full arguments. Archive, engine and project R-library locations have the same optional flags as the primary command. No hosted model or paid API calls occur.
