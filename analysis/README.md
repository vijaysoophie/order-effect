# analysis

Python implementation of the analyses reported in the paper, as Jupyter
notebooks with each step explained where it is carried out.

```
analysis/
├── orderfx.py          shared machinery
├── 01_preprocessing.ipynb
├── 02_fit_psychometric_functions.ipynb
├── 03_equality_tests.ipynb
├── 04_manuscript_figures.ipynb
├── requirements.txt
├── reference/          original FORTRAN/MATLAB results, for verification
└── outputs/            everything the notebooks produce
```

## Running it

```bash
pip install -r requirements.txt
jupyter lab
```

Run the notebooks in numerical order; each writes into `outputs/` and the next
reads from there. `outputs/` is committed, so the results can be read without
running anything.

## What each notebook does

**`01_preprocessing.ipynb`** — reads the raw per-trial files, drops trials
without a valid response, recodes the position of the standard as the position
of the test, converts grey levels to measured luminances, and counts for every
test luminance how many trials were run and how many drew a "same" response.
Writes `seq_data.txt` and `sim_data.txt`.

**`02_fit_psychometric_functions.ipynb`** — fits a psychometric function to
every cell of the design. Because an observer reports "same" when the test is
close enough to the standard *on either side*, the function is a peak rather
than a monotone curve, and the model is a difference of two Gaussian
cumulatives sharing one slope:

$$\Psi_\text{same}(x) = \Phi\big(\beta(x-\alpha_1)\big) - \Phi\big(\beta(x-\alpha_2)\big)$$

with *x* the log test luminance. It is fitted by maximum likelihood separately
for each test position and also to the two positions **aggregated** — the
conventional "ignore the order effect" baseline — giving
21 × 4 × 2 × 3 = 504 fits. Goodness of fit is the likelihood-ratio statistic
*G*². Writes `fit_all_python.csv`.

**`03_equality_tests.ipynb`** — asks the same questions of the raw counts
using the generalized Berry–Mielke statistic, which fits no curve at all. Two
comparisons: conditions 0 against 2 (a check on drift) and test-first against
test-second (a direct, model-free test for order effects).

**`04_manuscript_figures.ipynb`** — produces the figures in the paper and the
Score tests, *t* tests and correlation tests that accompany them. Also writes
`order_effects.csv`, the per-case Type A and Type B effects behind Figure 4.

## The measures

With α = (α₁ + α₂)/2 the point of subjective equality and σ = 1/β the spread:

| Measure | Definition | Meaning |
|---|---|---|
| **Type A** | 2(α<sub>1st</sub> − α<sub>2nd</sub>) / (σ<sub>1st</sub> + σ<sub>2nd</sub>) | shift in apparent brightness between positions, in units of the mean spread |
| **Type B** | log₂(β<sub>1st</sub> / β<sub>2nd</sub>) | difference in precision between positions |
| **DL** | exp(*x*₇₅) − exp(*x*₅₀) | difference limen, where *x*₅₀ = α and *x*₇₅ solves Φ₁(*x*) + Φ₂(*x*) = 1.5 |

Cells whose fit has fewer than one degree of freedom admit no goodness-of-fit
test and are excluded from analyses that use parameter estimates. They are not
excluded from the Berry–Mielke tests, which use only the counts.

## Outputs

```
outputs/
├── seq_data.txt, sim_data.txt       tallied counts (whitespace-delimited)
├── seq_data.csv, sim_data.csv       the same, with headers
├── fit_all_python.csv               parameter estimates for all 504 fits
├── order_effects.csv                per-case Type A and Type B effects
├── equality_conditions_0_vs_2.csv   Berry–Mielke tests, drift check
├── equality_across_orders.csv       Berry–Mielke tests, order effects
└── figures/
    ├── fit_all_python.pdf           21 pages, fitted functions per observer
    ├── equality_across_orders.pdf   21 pages, raw curves for the equality tests
    ├── fig03 … fig07, figA2         the manuscript figures (PNG and PDF)
    └── figure4_equality_tests.png   rejection counts
```

## Verification

The analyses were originally carried out in FORTRAN and MATLAB. `reference/`
holds the outputs of those implementations — `fit_all.csv` (the FORTRAN
parameter estimates) and the two MATLAB tally files — and every notebook ends
by comparing its own results against them. As committed:

- **Preprocessing** — the 1176 tallied rows per experiment are **identical**
  to the MATLAB files.
- **Fitting** — 500 of 504 fits agree on every parameter to within 1e-4, with
  a median absolute difference of 0; degrees of freedom and *G*² agree in all
  504.
- **Equality tests** — all nine values reported in the paper reproduce
  exactly.
- **Figures** — all 19 checked values from Figures 3, 4 and 5 match.

### The four cells that differ

| Observer | Mode | Condition | Position | Differs |
|---|---|---|---|---|
| 3 | sequential | 1 | 2nd | α₁ |
| 21 | sequential | 3 | 1st | α₁ |
| 21 | sequential | 3 | agg | α₁, β |
| 13 | simultaneous | 4 | right | β (df = −1) |

In the first three the observer said "different" at every test level below the
standard, so α₁ falls outside the tested range and the likelihood is
essentially **flat** in it — two very different values of α₁ give the same
fit, which is why α₂, *G*² and the degrees of freedom still agree. This is an
identifiability limit of the data, not a disagreement between implementations.
The fourth is an observer so precise that the fit is perfect, the degrees of
freedom come out negative and β is unconstrained; it is excluded from the
group analyses.

These cells are also why the sequential difference limens differ from the
published values in the third significant figure: the DL depends on α₁
directly, whereas Type A and Type B depend on it only through α and β. Setting
`USE_FORTRAN_FITS = True` at the top of notebook 04 runs the figures off
`reference/fit_all.csv` instead and reproduces the published DL figures
exactly.

## Implementation notes

- **Optimiser.** `scipy.optimize.minimize(method='SLSQP')` stands in for
  MATLAB's `fmincon` with the SQP algorithm.
- **Starting points.** 27 per fit, placed by the rule
  `linspace(lb, ub, 5)[1:-1]` so that no search begins on a boundary. Set
  `N_STARTS = 2` in notebook 02 for the abbreviated grid the MATLAB script
  used.
- **Condition numbering.** Folders on disk are `condition_0..3`; the tally
  files number conditions **1–4**; `fit_all.csv` and the paper use **0–3**.
  `cond` 1 ↔ condition 0 ↔ 26.4 cd/m² (the repeat), 2 ↔ 13.2, 3 ↔ 26.4,
  4 ↔ 39.5.
- **Subject numbers** are the 1-based index into `orderfx.NAMES`, which is the
  alphabetical order used by the original scripts. Do not reorder it.
- **Capitalisation is resolved case-insensitively** at every level of the data
  tree, for folders *and* for the response files inside them, because the two
  do not always agree (see `data/README.md`). On a case-sensitive filesystem
  an exact-match reader loses observers without reporting an error, so
  notebook 01 prints the observer count and the verification cell compares the
  tally against the reference files.
- **Exclusion rules differ by figure** and are transcribed from the original
  scripts; see the markdown above each figure in notebook 04.
