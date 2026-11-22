# R evidence and offer validation contract

## Current delivery boundary

The document application layer can write a versioned review exchange for R.
The exporter is ordinary Python code. It does not launch R, install packages,
fit a statistical model, invoke CUDA, or establish an independent R result.

The current environment has no R runtime. No executable R validation project
or fabricated renv lock is added by this guide. A real R installation,
generated dependency lock, environment binding, and executed comparison are
required before describing R integration as tested.

## Produce the current exchange

The source is `export_r_review` in
[the document application layer](../../pilot/document_offer_layer.py).
The [demo CLI](../../tools/run_document_offer.py) can write both the full
report and the review exchange to new paths:

    python tools/run_document_offer.py --backend cpu \
      --output .runs/document-offer-report.json \
      --r-export .runs/r-offer-review

Choose new paths on a subsequent run; the CLI protects existing output files
and export directories. This command demonstrates Python-side export only.
Follow the current module's tests and delivery report for observed run results.

The current exchange version is `br-r-offer-review/1` and contains:

- `offer_review.csv` — one row per case and offer.
- `manifest.json` — report identity, currency, time zone, money convention,
  exact-number convention, file hash and R execution status.

The exported case values are `baseline` and `after_evidence`. Only a valid
document-adjusted report is exportable. A pending, conflicting or otherwise
held document projection has no adjusted result to export.

## Column meanings

| Column | Meaning and required handling |
| --- | --- |
| `schema_version` | Require exactly the supported exchange version |
| `report_sha256` | Identify the full report whose digest is shared by every row |
| `deal_id` | Preserve as text; never combine separate deals by row position |
| `as_of` | Preserve the explicit analysis date |
| `currency` | Require the intended currency before any monetary comparison |
| `case` | Distinguish original and document-adjusted assumptions |
| `offer_id` | Join by ID with case and deal; do not rely on array order |
| `price_cents` | Integer cents for the proposed purchase price |
| `baseline_profit_cents` | Signed integer cents in the baseline economic scenario |
| `mean_profit_cents_numerator` | Exact base-10 integer string for conditional expected profit numerator |
| `mean_profit_cents_denominator` | Exact positive integer string denominator |
| `ev_cents_numerator` | Exact integer string for expected net cash per attempt, or empty if unknown |
| `ev_cents_denominator` | Exact positive integer string denominator, or empty with unknown EV |
| `policy_passed` | Literal true/false for the evaluated policy; not transaction approval |
| `execution_allowed` | False; exporting a research report does not authorize an acquisition |

The fraction numerator divided by its denominator is in cents. Dividing by
100 is a presentation conversion to dollars, not a new financial calculation.

Unknown EV uses two empty fields. It must remain unknown rather than become
zero, an inferred agreement probability, or a missing row dropped from an
average.

## Exactness and provenance

Treat rational numerator and denominator columns as character strings until
using an explicitly chosen exact or arbitrary-precision representation.
Ordinary R numeric doubles cannot preserve every possible integer. Do not
silently coerce an unbounded numerator to numeric.

Validate integer-cent ranges, signedness, missing values, and aggregate
overflow when choosing an R or Arrow representation. A type named int64
does not remove the need to check the concrete conversion behavior.

Before comparison:

1. Verify the CSV digest against the manifest.
2. Require the expected schema version, currency, and time-zone convention.
3. Require one report digest and unique deal/case/offer keys.
4. Resolve that digest to the full report and its input packet, evidence,
   source versions, bindings and scenario assumptions.
5. Preserve original and adjusted cases independently.
6. Record the actual R/Python/runtime versions and numeric conversion path.

The CSV is a review summary. It does not contain all scenario weights,
economic inputs, source claims or review events needed to recompute the
model independently. Use the complete Python report and its original
fixtures for that later independent calculation. Comparing summary outputs
alone cannot establish that the underlying formulas are correct.

## Future R implementation gate

When an R runtime is available, perform this bounded sequence:

1. Create a real project environment and generate its dependency lock using
   renv from the installed packages. Commit the actual lock and restore it
   on an independent environment before claiming reproducibility.
2. Select the intended Python environment explicitly for this project's
   authoritative engine calls. Record the resolved interpreter before any
   reticulate import and keep dependency/version evidence.
3. Build a typed reader for `br-r-offer-review/1` with the rules above.
   An Arrow/Parquet successor must have a separately versioned contract and
   demonstrate exact ID, time, null, and money round trips.
4. Recompute a small financial and probability case independently in R.
   Preserve the distinction between a validation reference and the
   authoritative operational implementation.
5. Compare exact values or justified tolerances in stated currency units,
   including equality boundaries that affect policy decisions.
6. Run negative cases: mismatched currency, duplicated keys, unknown EV,
   incorrect hash, out-of-range money, and a changed report digest.
7. Record execution evidence, differences, and unavailable optional GPU paths.

The official reticulate documentation now generally recommends dependency
declarations through `py_require()`. This project additionally requires an
explicitly identified Python runtime for validated shared-engine execution.
The documented `RETICULATE_PYTHON` setting is prescriptive when that
self-managed environment route is selected. Do not let a different Python
environment silently satisfy a validation run.

## Statistical research after the exchange works

Calibration research requires complete timestamped outcomes, including
rejected, expired, withdrawn, failed-to-close and pending cases. Use only
predictors available at the prediction cutoff and separate related
negotiations when evaluating generalization.

Time-to-event research needs an explicit start, observation window, event,
and censoring definition. Pending negotiations do not become rejections
merely because the dataset was exported today.

Probability scores, reliability plots, sample sizes and economic loss
diagnostics should complement one another. An agent's confidence or a
document-retrieval score is not an empirical acceptance probability.

R does not automatically execute on CUDA. An R caller can later invoke the
shared Python/CUDA batch interface, but actual GPU execution, precision
parity and measured performance require real device evidence.

## Primary references

- [renv project environments, snapshot and restore](https://rstudio.github.io/renv/articles/renv.html)
- [reticulate Python environment configuration](https://rstudio.github.io/reticulate/articles/versions.html)
- [Apache Arrow R typed tables and exchange](https://arrow.apache.org/docs/r/articles/arrow.html)
- [Probability calibration and score interpretation](https://scikit-learn.org/stable/modules/calibration.html)
- [R survival event and censoring representation](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/Surv.html)
