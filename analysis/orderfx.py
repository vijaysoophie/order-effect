"""
orderfx.py
==========

Shared helper functions for the Python port of the MATLAB order-effect analysis.

The MATLAB pipeline consists of three scripts:

    seq_preprocess.m       ->  seq_data.txt  (tally raw trials, sequential)
    sim_preprocess.m       ->  sim_data.txt  (tally raw trials, simultaneous)
    fit_all.m              ->  psychometric fits per subject/condition/order
    analyze_equality_*.m   ->  non-parametric tests of equality of functions
    fig03.m ... figA2.m    ->  the figures and statistics reported in the paper

This module contains the pieces that are shared between the notebooks:

  * constants (subject names, conditions, the RGB -> cd/m^2 lookup table)
  * `preprocess_task`  - port of seq_preprocess.m / sim_preprocess.m
  * `psi_same`         - the difference-of-Gaussians psychometric function
  * `fit_tim_2p`       - port of the `fit_TIM_2P_mod` maximum-likelihood fitter
  * `load_tally`       - reader for the intermediate whitespace-delimited files

Everything is written so that the notebooks can explain each step while the
mechanical details live here.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from itertools import product

import numpy as np
import pandas as pd
from scipy.optimize import minimize, brentq
from scipy.stats import norm, chi2, gamma as gamma_dist, t as t_dist

# ---------------------------------------------------------------------------
# Constants (transcribed from the MATLAB scripts)
# ---------------------------------------------------------------------------

#: Subject nicknames, in the order used by the MATLAB scripts.  The subject
#: *number* written into the tally files is simply the 1-based index here, so
#: this ordering must not be changed if results are to be comparable.
NAMES = ['Cap', 'Duck', 'Fit', 'Fox', 'Gren', 'Hero', 'Ike', 'Joke', 'Ken',
         'King', 'Kir', 'Kong', 'Link', 'Mac', 'Ness', 'Pit', 'Rob', 'Rock',
         'Roy', 'Sam', 'Snake']

#: RGB value of the standard (reference) patch in each of the four conditions.
#: Conditions are numbered 1..4 in the tally files (0..3 on disk).
STANDARD_RGB = [60, 30, 60, 90]

#: Same numbers again; in the MATLAB code `conds` is only used to build the
#: cosmetic "60_vs_60" condition label in column 4.
CONDS = [60, 30, 60, 90]

#: Measured luminance (cd/m^2) for every 8-bit grey level that was used in the
#: experiment.  Grey levels that never occurred map to NaN.
_LOOKUP_PAIRS = {
    20: 8.8, 23: 10.1, 26: 11.4, 30: 13.2, 34: 14.9, 40: 17.6, 45: 19.8,
    52: 22.4, 60: 26.4, 69: 30.3, 79: 34.7, 91: 39.96,
    59: 25.9, 68: 29.9, 78: 34.3, 90: 39.5,
    103: 45.2, 119: 52.3, 136: 59.7,
}

LOOKUP = np.full(256, np.nan)
for _k, _v in _LOOKUP_PAIRS.items():
    LOOKUP[_k] = _v

#: Column names of the intermediate tally files (see 00_readme.pdf).
TALLY_COLUMNS = ['sub_num', 'sub_code', 'cond', 'cond_label', 'standard',
                 'test_pos', 'test', 'total', 'same', 'diff']

#: Human-readable task names, index 0 = sequential, 1 = simultaneous.
TASK_LABELS = ['sequential', 'simultaneous']

#: Labels for the two presentation orders / locations, per task.
ORDER_LABELS = [['1st', '2nd', 'agg'],
                ['left', 'right', 'agg']]


# ---------------------------------------------------------------------------
# Step 1: preprocessing (port of seq_preprocess.m / sim_preprocess.m)
# ---------------------------------------------------------------------------

_RGBA_RE = re.compile(r'RGBA\(\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\)')


def _find_entry(parent: str, name: str, want_dir: bool = False) -> str | None:
    """Locate `name` inside `parent`, ignoring capitalisation.

    Capitalisation is not consistent in the data tree: a subject folder may be
    ``kir`` while the files inside it are named ``Kir_...``, and the two
    experiments disagree with each other about which form to use. macOS and
    Windows filesystems are case-insensitive and hide this, but on Linux --
    and therefore on most CI runners -- an exact-match lookup silently drops
    those observers. Matching case-insensitively here keeps the analysis
    working everywhere.
    """
    if not os.path.isdir(parent):
        return None
    target = name.lower()
    for entry in os.listdir(parent):
        if entry.lower() == target:
            path = os.path.join(parent, entry)
            if want_dir and not os.path.isdir(path):
                continue
            return path
    return None


def _find_response_file(rep_dir: str, cond_index: int) -> str | None:
    """Find the per-trial response file in a Repetition folder.

    The file is named ``<Subject>_condition_<k>_Repetition_1.txt``, but its
    subject prefix does not always match the capitalisation of the folder it
    sits in, so it is matched on the invariant part of the name. The sibling
    ``trials_*`` and ``conditions_*`` files end in ``_rep_1.txt`` rather than
    ``_Repetition_1.txt`` and so are not matched.
    """
    if not os.path.isdir(rep_dir):
        return None
    suffix = f'_condition_{cond_index}_repetition_1.txt'
    for entry in sorted(os.listdir(rep_dir)):
        if entry.lower().endswith(suffix):
            return os.path.join(rep_dir, entry)
    return None


def read_raw_trial_file(path: str) -> pd.DataFrame:
    """Read one raw per-trial file and return the eight columns MATLAB keeps.

    A raw line looks like::

        129, 1, 2, 1, RGBA(60, 60, 60, 255), RGBA(0, 0, 0, 160), RGBA(52, ...)

    MATLAB's ``readtable`` splits this naively on commas, producing 20 columns,
    and ``removevars(raw_data,[5 7:9 11:13 15:17 19:20])`` then keeps columns
    1, 2, 3, 4, 6, 10, 14 and 18 -- i.e. the four leading integers plus the
    *green* channel of each of the four RGBA groups.  Because all patches are
    achromatic (R = G = B), taking the green channel is the same as taking the
    grey level.  We parse the RGBA groups properly and pick the same values.

    Returned columns
    ----------------
    order     trial presentation order (used only for sorting)
    std_pos   interval/location that held the *standard*  (1 or 2)
    true      the objectively correct response
    resp      observer's response: 1 = "same", 2 = "different"
    sqr1      grey level of the patch in interval/location 1
    bckg1     grey level of its background
    sqr2      grey level of the patch in interval/location 2
    bckg2     grey level of its background
    """
    rows = []
    with open(path, 'r') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            head = line.split('RGBA')[0]
            leading = [int(v) for v in head.strip().rstrip(',').split(',')]
            groups = _RGBA_RE.findall(line)
            if len(leading) < 4 or len(groups) < 4:
                continue
            # groups are (square1, background1, square2, background2);
            # index [1] of each group is the green channel = the grey level.
            greys = [int(g[1]) for g in groups[:4]]
            rows.append(leading[:4] + greys)

    return pd.DataFrame(
        rows, columns=['order', 'std_pos', 'true', 'resp',
                       'sqr1', 'bckg1', 'sqr2', 'bckg2'])


def tally_one_file(path: str, min_levels: int = 4):
    """Tally one raw file into (test_pos, test_grey, total, same, diff) records.

    This is the inner loop of the MATLAB preprocessing scripts:

    1. keep only trials with a valid response (1 = same, 2 = different);
    2. convert the *standard* position into the *test* position via
       ``test_pos = 3 - std_pos``;
    3. split the trials by the position of the test (1 or 2);
    4. within each split, count for every distinct test grey level how many
       trials were run and how many drew a "same" response;
    5. drop the split entirely if it contains fewer than four test levels
       (too few points to fit a three-parameter function).
    """
    raw = read_raw_trial_file(path)
    if raw.empty:
        return []

    raw = raw.sort_values('order', kind='mergesort').reset_index(drop=True)
    raw = raw[raw['resp'].isin([1, 2])].copy()
    raw['test_pos'] = 3 - raw['std_pos']          # standard pos -> test pos

    out = []
    for iorder in (1, 2):
        # If the test sat in position 1 its grey level is in `sqr1`, etc.
        col_test = 'sqr1' if iorder == 1 else 'sqr2'
        block = raw[raw['test_pos'] == iorder]
        if block.empty:
            continue
        levels = np.sort(block[col_test].unique())
        if len(levels) < min_levels:
            continue
        for lev in levels:
            at_level = block[block[col_test] == lev]
            total = len(at_level)
            same = int((at_level['resp'] == 1).sum())
            out.append((iorder, int(lev), total, same, total - same))
    return out


def preprocess_task(data_root: str, out_path: str | None = None,
                    names: list[str] | None = None) -> pd.DataFrame:
    """Port of ``seq_preprocess.m`` / ``sim_preprocess.m``.

    Parameters
    ----------
    data_root : path to ``SequentialEffect-main/Data`` or
                ``SpaceOrderEffect-main/Data``.
    out_path  : if given, the tally is also written as a whitespace-delimited
                text file in exactly the MATLAB format.
    names     : subject nicknames; defaults to :data:`NAMES`.

    Returns a tidy DataFrame with the ten columns described in 00_readme.pdf.
    """
    names = names or NAMES
    records = []

    for suj, name in enumerate(names, start=1):
        subject_dir = _find_entry(data_root, name, want_dir=True)
        if subject_dir is None:
            continue
        for icond in range(1, len(STANDARD_RGB) + 1):
            cond_dir = _find_entry(subject_dir, f'condition_{icond - 1}',
                                   want_dir=True)
            if cond_dir is None:
                continue
            rep_dir = _find_entry(cond_dir, 'Repetition_1', want_dir=True)
            if rep_dir is None:
                continue
            filename = _find_response_file(rep_dir, icond - 1)
            if filename is None:
                continue
            for iorder, lev, total, same, diff in tally_one_file(filename):
                records.append({
                    'sub_num': suj,
                    'sub_code': name,
                    'cond': icond,
                    'cond_label': f'{CONDS[icond - 1]}_vs_{CONDS[icond - 1]}',
                    'standard': LOOKUP[STANDARD_RGB[icond - 1]],
                    'test_pos': iorder,
                    'test': LOOKUP[lev],
                    'total': total,
                    'same': same,
                    'diff': diff,
                })

    df = pd.DataFrame(records, columns=TALLY_COLUMNS)
    if out_path is not None:
        write_tally(df, out_path)
    return df


def _fmt_num(x: float) -> str:
    """Format a float the way MATLAB's ``num2str`` does for these values."""
    if float(x).is_integer():
        return str(int(x))
    return f'{x:g}'


def write_tally(df: pd.DataFrame, path: str) -> None:
    """Write the tally DataFrame in the exact whitespace-delimited MATLAB format."""
    with open(path, 'w') as fh:
        for _, r in df.iterrows():
            fh.write(' '.join([
                str(int(r.sub_num)), r.sub_code, str(int(r['cond'])),
                r.cond_label, _fmt_num(r.standard), str(int(r.test_pos)),
                _fmt_num(r.test), str(int(r.total)), str(int(r['same'])),
                str(int(r['diff'])),
            ]) + '\n')


def load_tally(path: str) -> pd.DataFrame:
    """Read a whitespace-delimited tally file (``seq_data.txt`` / ``sim_data.txt``)."""
    return pd.read_csv(path, sep=r'\s+', header=None, names=TALLY_COLUMNS)


# ---------------------------------------------------------------------------
# Step 2: the psychometric model and its maximum-likelihood fit
# ---------------------------------------------------------------------------

def psi_same(x, beta, alpha1, alpha2):
    """Probability of a "same" response.

    The model is a *difference of two Gaussian cumulatives* sharing a common
    slope parameter ``beta``:

        P(same | x) = Phi((x - alpha1) * beta) - Phi((x - alpha2) * beta)

    ``x`` is the log test luminance.  ``alpha1`` and ``alpha2`` are the lower
    and upper boundaries of the interval of test values that are judged "same"
    as the standard, and ``1/beta`` is the standard deviation of the underlying
    Gaussians (so larger ``beta`` = sharper transitions = more precise
    observer).  The distance ``alpha2 - alpha1`` is the *width* of the
    "same" region and ``(alpha1 + alpha2)/2`` is its centre, the quantity used
    later as the point of subjective equality.
    """
    x = np.asarray(x, dtype=float)
    sd = 1.0 / beta
    return norm.cdf(x, alpha1, sd) - norm.cdf(x, alpha2, sd)


def _neg_log_likelihood(p, same, diff, lev):
    """Negative log-likelihood of the binomial same/different counts."""
    beta, alpha1, width = p
    alpha2 = alpha1 + width
    p_same = np.clip(psi_same(lev, beta, alpha1, alpha2), 0.0, 1.0)
    p_diff = np.clip(1.0 - p_same, 0.0, 1.0)
    with np.errstate(divide='ignore', invalid='ignore'):
        terms = np.concatenate([same * np.log(p_same), diff * np.log(p_diff)])
    L = -np.nansum(terms)          # MATLAB uses nansum: 0*log(0) -> ignored
    if not np.isfinite(L):
        return np.finfo(float).max
    return L


@dataclass
class FitResult:
    """Container mirroring the struct returned by ``fit_TIM_2P_mod``."""
    Beta: float
    Alpha_1: float
    Alpha_2: float
    LikelihoodRatioStatistic: float
    DegreesOfFreedom: int
    LikelihoodRatioP_value: float
    BoundariesReached: str
    NegLogLikelihood: float

    def as_dict(self):
        return asdict(self)


def fit_tim_2p(levels, same, diff,
               beta_bounds=(1.0, 14.0),
               alpha1_bounds=None,
               width_bounds=(0.0, 5.0),
               beta_start=(3.0, 8.0),
               alpha1_start=None,
               width_start=(1.5,)) -> FitResult:
    """Maximum-likelihood fit of the difference-of-Gaussians model.

    Python port of ``fit_TIM_2P_mod`` in ``fit_all.m`` (itself adapted from the
    supplementary material of https://doi.org/10.3389/fpsyg.2017.01142).

    The three free parameters are ``beta``, ``alpha1`` and ``width``, with
    ``alpha2 = alpha1 + width`` enforced by construction so that the ordering
    constraint alpha1 <= alpha2 never has to be checked.

    The optimiser is run from every combination of the supplied starting values
    (a grid search over starting points, to guard against local minima) and the
    run with the lowest negative log-likelihood wins.  MATLAB uses ``fmincon``
    with the SQP algorithm; SciPy's ``minimize(method='SLSQP')`` is the direct
    equivalent for a bound-constrained smooth problem.

    Goodness of fit is the likelihood-ratio statistic

        G^2 = 2 * sum( O * log(O / E) )

    with expected counts E from the fitted function, compared against a
    chi-square distribution.  Following the MATLAB code, cells with an expected
    count of 0.06 or less are dropped from the degrees of freedom.
    """
    lev = np.asarray(levels, dtype=float)
    same = np.asarray(same, dtype=float)
    diff = np.asarray(diff, dtype=float)

    if alpha1_bounds is None:
        alpha1_bounds = (lev.min(), lev.max())
    if alpha1_start is None:
        alpha1_start = (float(np.mean(lev)),)

    beta_bounds = tuple(sorted(beta_bounds))
    alpha1_bounds = tuple(sorted(alpha1_bounds))
    width_bounds = tuple(sorted(width_bounds))
    bounds = [beta_bounds, alpha1_bounds, width_bounds]

    best = None
    for b0, a0, w0 in product(np.atleast_1d(beta_start),
                              np.atleast_1d(alpha1_start),
                              np.atleast_1d(width_start)):
        x0 = [np.clip(b0, *beta_bounds),
              np.clip(a0, *alpha1_bounds),
              np.clip(w0, *width_bounds)]
        try:
            res = minimize(_neg_log_likelihood, x0, args=(same, diff, lev),
                           method='SLSQP', bounds=bounds,
                           options={'maxiter': 500, 'ftol': 1e-10})
        except Exception:
            continue
        if not np.isfinite(res.fun):
            continue
        if best is None or res.fun < best.fun:
            best = res

    if best is None:                                  # should not happen
        raise RuntimeError('all optimiser starts failed')

    beta, alpha1, width = best.x
    alpha2 = alpha1 + width

    # --- which parameters ended up sitting on a boundary? -------------------
    tol = 1e-8
    warn = []
    for val, (lo, hi), nm in zip(best.x, bounds, ['Beta', 'Alpha_1', 'Width']):
        if abs(val - lo) < tol:
            warn.append(f'lower_{nm}')
        if abs(val - hi) < tol:
            warn.append(f'upper_{nm}')
    warn_str = ' ' + ' '.join(warn) + ' ' if warn else ' none '

    # --- goodness of fit ----------------------------------------------------
    n_obs = same + diff
    p_s = np.clip(psi_same(lev, beta, alpha1, alpha2), 0.0, 1.0)
    p_d = np.clip(1.0 - p_s, 0.0, 1.0)
    O = np.concatenate([same, diff])
    E = np.concatenate([p_s * n_obs, p_d * n_obs])
    df = int((n_obs > 0).sum()) - 3 - int((E <= 0.06).sum())
    mask = E > 0
    with np.errstate(divide='ignore', invalid='ignore'):
        G2 = 2.0 * np.nansum(O[mask] * np.log(O[mask] / E[mask]))
    p_value = 1.0 if df < 1 else float(1.0 - chi2.cdf(G2, df))

    return FitResult(Beta=float(beta), Alpha_1=float(alpha1),
                     Alpha_2=float(alpha2),
                     LikelihoodRatioStatistic=float(G2),
                     DegreesOfFreedom=df,
                     LikelihoodRatioP_value=p_value,
                     BoundariesReached=warn_str,
                     NegLogLikelihood=float(best.fun))


# ---------------------------------------------------------------------------
# Step 2b: assembling the data for one (subject, condition, task, order) cell
# ---------------------------------------------------------------------------

def get_cell(data: pd.DataFrame, sub: int, cond: int, order: int) -> pd.DataFrame:
    """Return the psychometric data for one cell of the design.

    ``order`` is 1 (test 1st / left), 2 (test 2nd / right) or 3 (aggregated).
    For the aggregated case the trial counts of the two orders are added
    level-by-level, exactly as ``fit_all.m`` does.
    """
    sel = data[(data.sub_num == sub) & (data['cond'] == cond)]
    if order in (1, 2):
        take = sel[sel.test_pos == order].sort_values('test')
        out = pd.DataFrame({
            'log_test': np.log(take['test'].to_numpy()),
            'log_standard': np.log(take['standard'].to_numpy()),
            'total': take['total'].to_numpy(),
            'same': take['same'].to_numpy(),
            'diff': take['diff'].to_numpy(),
        })
        return out

    t1 = sel[sel.test_pos == 1].sort_values('test')
    t2 = sel[sel.test_pos == 2].sort_values('test')
    if len(t1) == 0 or len(t2) == 0 or len(t1) != len(t2):
        return pd.DataFrame(columns=['log_test', 'log_standard',
                                     'total', 'same', 'diff'])
    return pd.DataFrame({
        'log_test': np.log(t1['test'].to_numpy()),
        'log_standard': np.log(t1['standard'].to_numpy()),
        'total': t1['total'].to_numpy() + t2['total'].to_numpy(),
        'same': t1['same'].to_numpy() + t2['same'].to_numpy(),
        'diff': t1['diff'].to_numpy() + t2['diff'].to_numpy(),
    })


#: Special-case bounds / starting values hard-coded in ``fit_all.m`` for a few
#: cells where the default search failed.  Keyed by (sub, cond, task, order)
#: with task 1 = sequential, 2 = simultaneous.
SPECIAL_CASES = {
    (13, 4, 2, 2): {'beta_bounds': (2.0, 50.0)},
    (3, 1, 1, 2): {'alpha1_scale_bounds': (0.05, 4.0), 'alpha1_scale_start': 0.1},
    (21, 3, 1, 1): {'alpha1_scale_bounds': (0.05, 4.0), 'alpha1_scale_start': 0.1},
}


def interior_starts(bounds, n: int = 3) -> np.ndarray:
    """The FORTRAN rule for placing starting points inside a parameter's range.

    To obtain ``n`` starting values, lay down ``n + 2`` equally spaced points
    between the lower and upper bound and discard the two end points, so that
    no search is ever started *on* a boundary::

        linspace(lb, ub, n + 2)[1:-1]

    For ``n = 3`` and bounds ``[1, 14]`` this gives 4.25, 7.5 and 10.75.
    """
    lo, hi = sorted(bounds)
    return np.linspace(lo, hi, n + 2)[1:-1]


def fit_cell(cell: pd.DataFrame, sub: int, cond: int, task: int, order: int,
             n_starts: int = 3) -> FitResult:
    """Fit one design cell using the bounds and starting values of ``fit_all.m``.

    ``n_starts`` selects the starting-point scheme:

    * ``3`` (default) reproduces the **FORTRAN** code: 3 interior starting
      points per parameter, placed by :func:`interior_starts`, giving a
      3 x 3 x 3 = 27-point grid.
    * ``2`` reproduces the abbreviated grid of ``fit_all.m``: 2 starts for
      ``beta``, 1 for ``alpha1`` (at the standard) and 1 for the width.
    """
    standard = float(cell['log_standard'].iloc[0])
    special = SPECIAL_CASES.get((sub, cond, task, order), {})

    beta_bounds = special.get('beta_bounds', (1.0, 14.0))
    a_lo, a_hi = special.get('alpha1_scale_bounds', (0.25, 4.0))
    alpha1_bounds = (standard * a_lo, standard * a_hi)
    width_bounds = (0.0, 5.0)

    if n_starts >= 3:
        # Starting points are derived from the bounds themselves, so the
        # hand-tuned `alpha1_scale_start` of fit_all.m is not needed here:
        # widening alpha1's bounds automatically moves its starting points.
        beta_start = interior_starts(beta_bounds, n_starts)
        alpha1_start = interior_starts(alpha1_bounds, n_starts)
        width_start = interior_starts(width_bounds, n_starts)
    else:
        alpha1_centre = standard * special.get('alpha1_scale_start', 1.0)
        beta_start = np.array([3.0, 8.0])
        alpha1_start = np.array([alpha1_centre])
        width_start = np.array([1.5])

    return fit_tim_2p(cell['log_test'].to_numpy(),
                      cell['same'].to_numpy(),
                      cell['diff'].to_numpy(),
                      beta_bounds=beta_bounds,
                      alpha1_bounds=alpha1_bounds,
                      width_bounds=width_bounds,
                      beta_start=beta_start,
                      alpha1_start=alpha1_start,
                      width_start=width_start)


# ---------------------------------------------------------------------------
# Step 3: derived measures (Type A, Type B effects)
# ---------------------------------------------------------------------------

def type_a_effect(a1_o1, a2_o1, beta_o1, a1_o2, a2_o2, beta_o2):
    """Type A (shift) effect: difference in PSE, in units of the mean spread.

        alpha_k = (alpha1_k + alpha2_k) / 2            (PSE for order k)
        sigma_k = 1 / beta_k                           (spread for order k)
        Type A  = 2 (alpha_1 - alpha_2) / (sigma_1 + sigma_2)

    A negative value means the test looked *dimmer* when presented first/left.

    The difference in location is expressed in units of the mean spread of the
    two functions so that observers of differing precision are comparable; see
    ``fig04.m`` and the corresponding definition in the paper.
    """
    alpha_o1 = (np.asarray(a1_o1) + np.asarray(a2_o1)) / 2.0
    alpha_o2 = (np.asarray(a1_o2) + np.asarray(a2_o2)) / 2.0
    spread = 1.0 / np.asarray(beta_o1) + 1.0 / np.asarray(beta_o2)
    return 2.0 * (alpha_o1 - alpha_o2) / spread


def difference_limen(alpha1, alpha2, beta):
    """Difference limen in native (cd/m^2) units, per Appendix A.

    The psychometric function for the greater-less format implied by our
    same-different fit is ``Psi(x) = [Phi_1(x) + Phi_2(x)] / 2`` (Eq. A1.2), so

      * the 50% point is ``x50 = (alpha1 + alpha2) / 2`` in closed form;
      * the 75% point ``x75`` solves ``Phi_1(x) + Phi_2(x) - 1.5 = 0`` and has
        to be found numerically.

    Both are in log luminance, and the DL is returned in native units as
    ``exp(x75) - exp(x50)``, matching ``fig05.m`` / ``fig06.m`` / ``fig07.m``.
    """
    alpha1 = np.atleast_1d(np.asarray(alpha1, dtype=float))
    alpha2 = np.atleast_1d(np.asarray(alpha2, dtype=float))
    beta = np.atleast_1d(np.asarray(beta, dtype=float))
    out = np.empty(len(alpha1))
    for i, (a1, a2, b) in enumerate(zip(alpha1, alpha2, beta)):
        sd = 1.0 / b
        f = lambda x: norm.cdf(x, a1, sd) + norm.cdf(x, a2, sd) - 1.5
        hi = a2 + 10.0 * sd + 1.0
        while f(hi) < 0:                    # widen until the root is bracketed
            hi += 10.0 * sd + 1.0
        x75 = brentq(f, a2, hi, xtol=1e-12)
        out[i] = np.exp(x75) - np.exp((a1 + a2) / 2.0)
    return out if len(out) > 1 else out[0]


# ---------------------------------------------------------------------------
# Statistical tests used by the figure scripts (fig03.m ... fig07.m)
# ---------------------------------------------------------------------------

def score_test(successes, n, p0=0.5, alpha=0.05):
    """One-sample Score test for a proportion, with the Wilson interval.

    This is the test the figure scripts print to the console (Wilson, 1927;
    see García-Pérez, 2005; Newcombe, 1998a). The statistic uses the *null*
    standard error, while the interval is the Wilson score interval, so the
    two are consistent with one another.
    """
    p = successes / n
    z = (p - p0) / np.sqrt(p0 * (1 - p0) / n)
    p_value = 2 * norm.cdf(-abs(z))
    zc = norm.ppf(1 - alpha / 2)
    zc2 = zc ** 2
    num1 = 2 * n * p + zc2
    num2 = zc * np.sqrt(4 * n * p * (1 - p) + zc2)
    den = 2 * (n + zc2)
    return {'proportion': p, 'count': successes, 'n': n, 'z': z,
            'p_value': p_value, 'CI': ((num1 - num2) / den, (num1 + num2) / den)}


def one_sample_t(x, alpha=0.05):
    """One-sample t test, reporting the SD the way the MATLAB scripts do.

    ``std(x,1)`` in MATLAB normalises by N, so the scripts report a population
    SD and then form the standard error as ``sd / sqrt(n-1)``. That is
    algebraically the usual ``s / sqrt(n)``, so the t statistic matches
    ``scipy.stats.ttest_1samp``; only the printed SD differs.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    m = x.mean()
    sd_pop = x.std(ddof=0)
    se = sd_pop / np.sqrt(n - 1)
    t = m / se
    p_value = 2 * t_dist.cdf(-abs(t), n - 1)
    tc = t_dist.ppf(1 - alpha / 2, n - 1)
    return {'mean': m, 'sd': sd_pop, 't': t, 'df': n - 1, 'p_value': p_value,
            'CI': (m - tc * se, m + tc * se)}


def paired_t(x, y, alpha=0.05):
    """Paired-samples t test in the form used by ``fig05.m``."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    d = x - y
    m = d.mean()
    se = d.std(ddof=0) / np.sqrt(n - 1)
    t = m / se
    tc = t_dist.ppf(1 - alpha / 2, n - 1)
    return {'mean_x': x.mean(), 'sd_x': x.std(ddof=0),
            'mean_y': y.mean(), 'sd_y': y.std(ddof=0),
            'correlation': float(np.corrcoef(x, y)[0, 1]),
            'difference': m, 't': t, 'df': n - 1,
            'p_value': 2 * t_dist.cdf(-abs(t), n - 1),
            'CI': (m - tc * se, m + tc * se)}


def correlation_test(x, y, alpha=0.05):
    """Test that a product-moment correlation is zero, with a Fisher-z CI.

    Note the MATLAB scripts use ``zcrit*2/sqrt(n-3)`` for the half-width on
    the Fisher scale, i.e. twice the usual ``zcrit/sqrt(n-3)``; that choice is
    reproduced here so the printed intervals match.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    r = float(np.corrcoef(x, y)[0, 1])
    t = r * np.sqrt(n - 2) / np.sqrt(1 - r ** 2)
    p_value = 2 * t_dist.cdf(-abs(t), n - 2)
    term1 = (1 + r) / (1 - r)
    term2 = norm.ppf(1 - alpha / 2) * 2 / np.sqrt(n - 3)
    lo = (term1 * np.exp(-term2) - 1) / (term1 * np.exp(-term2) + 1)
    hi = (term1 * np.exp(term2) - 1) / (term1 * np.exp(term2) + 1)
    return {'r': r, 't': t, 'df': n - 2, 'p_value': p_value, 'CI': (lo, hi)}


def concordance_correlation(x, y):
    """Lin's (1989) concordance correlation coefficient.

        r_c = 2 r s_x s_y / (s_x^2 + s_y^2 + (mean_x - mean_y)^2)

    Unlike the product-moment correlation this penalises departures from the
    identity line, not merely from linearity, which is why the figure scripts
    print both.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    r = float(np.corrcoef(x, y)[0, 1])
    return (2 * r * x.std(ddof=0) * y.std(ddof=0)
            / (x.var(ddof=0) + y.var(ddof=0) + (x.mean() - y.mean()) ** 2))


def type_b_effect(beta_o1, beta_o2):
    """Type B (precision) effect: ``log2(beta_1 / beta_2)``.

    Positive means the observer was more precise when the test came
    first / on the left.
    """
    return np.log2(np.asarray(beta_o1) / np.asarray(beta_o2))


# ---------------------------------------------------------------------------
# Step 4: non-parametric tests of equality of psychometric functions
# (port of PF_test in analyze_equality_1.m / analyze_equality_2.m)
# ---------------------------------------------------------------------------

def _falling_factorials(v, m_max):
    """Columns 1..m_max of falling factorials: v, v(v-1), v(v-1)(v-2), ..."""
    v = np.asarray(v, dtype=float)
    out = np.empty((len(v), m_max + 1))
    out[:, 0] = np.nan            # index 0 unused (1-based bookkeeping)
    out[:, 1] = v
    for m in range(2, m_max + 1):
        out[:, m] = out[:, m - 1] * (v - m + 1)
    return out


def _marginal_terms(marg, count, N):
    """Build the R (or C) coefficient table of the Berry-Mielke moments.

    `marg` is the vector of row (or column) marginal totals, `count` is its
    length (I or J) and `N` the table total.  Returns a 7x7 array indexed from
    1, matching the MATLAB variables R(m,k) / C(m,k).
    """
    marg = np.asarray(marg, dtype=float)
    M = _falling_factorials(marg, 6)
    R = np.full((7, 7), np.nan)
    K = count

    for m in range(1, 5):
        R[m, 1] = np.sum(M[:, m] / marg ** 2)
    R[2, 2] = K * (K - 1)
    R[3, 2] = (K - 1) * (N - K)
    R[4, 2] = (N - K) ** 2 + 2 * N - K - np.sum(marg ** 2)
    for m in range(1, 7):
        R[m, 3] = np.sum(M[:, m] / marg ** 3)
    for m in range(3, 7):
        R[m, 4] = np.sum(M[:, m - 2] * (N - marg - K + 1) / marg ** 2)
    for m in range(2, 6):
        R[m, 5] = (K - 1) * R[m - 1, 1]
    R[3, 6] = K * (K - 1) * (K - 2)
    R[4, 6] = (K - 1) * (K - 2) * (N - K)
    R[5, 6] = (K - 2) * R[4, 2]
    R[6, 6] = np.sum((marg - 1) * (N - marg - K + 1) * (N - 2 * marg - K + 2))
    return R


def _prod_range(lo, hi):
    """MATLAB ``prod(lo:hi)``; an empty range gives 1."""
    if hi < lo:
        return 1.0
    return float(np.prod(np.arange(lo, hi + 1, dtype=float)))


def berry_mielke(tables):
    """Generalized Berry-Mielke test of equality of psychometric functions.

    Python port of the ``'G'`` branch of ``PF_test`` (García-Pérez &
    Núñez-Antón, 2018, Behavior Research Methods, 50, 2226-2255).

    Parameters
    ----------
    tables : sequence of 2-D integer arrays, one per stimulus level (stratum).
        Rows are populations (e.g. condition 0 vs condition 2, or test-first
        vs test-second) and columns are response categories (same, different).

    Returns
    -------
    dict with the omnibus ``G``, the gamma shape parameter ``c``, the
    ``p_value`` (None when no stratum is usable), and per-stratum diagnostics.

    Notes
    -----
    The test works stratum by stratum.  For each one it computes Pearson's
    statistic adjusted to ``T = X^2 (N-1)/N``, then standardises it using the
    *exact* first three moments of its permutation distribution under the null
    of equal populations.  A gamma approximation matched to that skewness
    turns each stratum into a gamma variate, and the strata are then combined
    by summing.  Strata whose skewness is below 0.5 are dropped, because the
    gamma approximation is unreliable there; so are degenerate strata that
    admit only a single permutation.
    """
    n_tab = len(tables)
    ids = np.arange(1, n_tab + 1)
    Tmean = np.full(n_tab, np.nan)
    Tvar = np.full(n_tab, np.nan)
    Tskew = np.full(n_tab, np.nan)
    Tstat = np.full(n_tab, np.nan)
    Zstat = np.full(n_tab, np.nan)
    Gstat = np.full(n_tab, np.nan)
    c_k = np.full(n_tab, np.nan)
    usable = np.ones(n_tab, dtype=bool)
    n_k = np.full(n_tab, np.nan)
    used_tables = [None] * n_tab

    for it, raw in enumerate(tables):
        raw = np.asarray(raw, dtype=float)
        N = raw.sum()
        n_k[it] = N
        # drop all-zero rows and columns, then recompute the marginals
        keep_r = raw.sum(axis=1) > 0
        keep_c = raw.sum(axis=0) > 0
        tab = raw[np.ix_(keep_r, keep_c)]
        row = tab.sum(axis=1)
        col = tab.sum(axis=0)
        I, J = len(row), len(col)

        # degenerate strata admitting a single permutation carry no information
        if J == 1 or (J == 2 and np.all(row == row[0]) and np.any(col == 1)):
            usable[it] = False
        if I == 1 or (I == 2 and np.all(col == col[0]) and np.any(row == 1)):
            usable[it] = False
        if not usable[it]:
            continue

        used_tables[it] = tab
        R = _marginal_terms(row, I, N)
        C = _marginal_terms(col, J, N)
        N1 = {m: _prod_range(N - 3, N - 4 + m) for m in range(1, 5)}
        N2 = {m: _prod_range(N - 5, N - 6 + m) for m in range(1, 7)}

        A = ((R[4, 1] + R[4, 2]) * (C[4, 1] + C[4, 2])
             + 2 * N1[1] * (2 * R[3, 1] * C[3, 1]
                            + (R[3, 1] + R[3, 2]) * (C[3, 1] + C[3, 2]))
             + N1[2] * (6 * R[2, 1] * C[2, 1]
                        + (R[2, 1] + R[2, 2]) * (C[2, 1] + C[2, 2]))
             + N1[3] * R[1, 1] * C[1, 1]) / N1[4]

        B = ((R[6, 3] + 3 * R[6, 4] + R[6, 6])
             * (C[6, 3] + 3 * C[6, 4] + C[6, 6])
             + 3 * N2[1] * (4 * (R[5, 3] + R[5, 4]) * (C[5, 3] + C[5, 4])
                            + (R[5, 3] + 2 * R[5, 4] + R[5, 5] + R[5, 6])
                            * (C[5, 3] + 2 * C[5, 4] + C[5, 5] + C[5, 6]))
             + N2[2] * (32 * R[4, 3] * C[4, 3]
                        + 18 * (R[4, 3] + R[4, 4]) * (C[4, 3] + C[4, 4])
                        + 12 * (R[4, 3] + R[4, 5]) * (C[4, 3] + C[4, 5])
                        + 3 * (R[4, 3] + R[4, 4] + 2 * R[4, 5] + R[4, 6])
                        * (C[4, 3] + C[4, 4] + 2 * C[4, 5] + C[4, 6]))
             + N2[3] * (68 * R[3, 3] * C[3, 3]
                        + 3 * (R[3, 3] + R[3, 4]) * (C[3, 3] + C[3, 4])
                        + 18 * (R[3, 3] + R[3, 5]) * (C[3, 3] + C[3, 5])
                        + (R[3, 3] + 3 * R[3, 5] + R[3, 6])
                        * (C[3, 3] + 3 * C[3, 5] + C[3, 6]))
             + N2[4] * (28 * R[2, 3] * C[2, 3]
                        + 3 * (R[2, 3] + R[2, 5]) * (C[2, 3] + C[2, 5]))
             + N2[5] * R[1, 3] * C[1, 3]) / N2[6]

        ET2 = A * (N - 1) ** 2 - (N + 2 * I * J - 2 * I - 2 * J + 1) * (N - 1)
        ET3 = ((B - 3 * A) * (N - 1) ** 3
               + (2 * N + 3 * I * J - 3 * I - 3 * J + 1) * (N - 1) ** 2)
        t_mean = (I - 1) * (J - 1)
        t_var = ET2 - t_mean ** 2
        t_skew = (ET3 - 3 * t_var * t_mean - t_mean ** 3) / (np.sqrt(t_var) ** 3)

        expected = np.outer(row, col) / N
        t_stat = np.sum((tab - expected) ** 2 / expected) * (N - 1) / N
        z_stat = (t_stat - t_mean) / np.sqrt(t_var)
        a = -2.0 / t_skew
        b = t_skew / 2.0
        c = 4.0 / t_skew ** 2

        Tmean[it], Tvar[it], Tskew[it] = t_mean, t_var, t_skew
        Tstat[it], Zstat[it] = t_stat, z_stat
        Gstat[it] = (z_stat - a) / b
        c_k[it] = c

    with np.errstate(invalid='ignore'):
        take = usable & (Tskew >= 0.5)

    if take.any():
        sum_c = np.nansum(c_k[take])
        sum_G = np.nansum(Gstat[take])
        p_value = float(gamma_dist.sf(sum_G, a=sum_c, scale=1.0))
        excluded = list(ids[~take])
    else:
        sum_c = sum_G = p_value = None
        excluded = list(ids)

    return {
        'NumTables': n_tab,
        'SampleSizes': n_k,
        'T_stats': Tstat, 'mu_T': Tmean, 'var_T': Tvar, 'gamma_T': Tskew,
        'Z_stats': Zstat, 'G_stats': Gstat,
        'omnibusG': sum_G, 'c_parameter': sum_c, 'p_value': p_value,
        'ExcludedTables': excluded,
        'data_used': used_tables,
    }


def mantel_haenszel(tables):
    """Generalized Mantel-Haenszel test (the ``'Q'`` branch of ``PF_test``).

    Provided for completeness; the two analysis scripts use the Berry-Mielke
    statistic. With a single stratum ``Q_GMH`` reduces to Pearson's statistic
    adjusted by ``(N-1)/N``, which the notebook uses as a check.
    """
    tables = [np.asarray(t, dtype=float) for t in tables]
    nrow, ncol = tables[0].shape
    row_tot = np.zeros(nrow)
    col_tot = np.zeros(ncol)
    R, C, N, E = [], [], [], []
    for t in tables:
        r = t.sum(axis=1)
        c = t.sum(axis=0)
        n = c.sum()
        R.append(r); C.append(c); N.append(n)
        E.append(np.outer(r, c) / n)
        row_tot += r
        col_tot += c
    I = int((row_tot > 0).sum())
    J = int((col_tot > 0).sum())
    if I == 1 or J == 1:
        return {'Q_GMH': None, 'degrees_of_freedom': None, 'p_value': None}

    dim = (I - 1) * (J - 1)
    s1 = np.zeros(dim)
    s2 = np.zeros((dim, dim))
    for t, r, c, n, e in zip(tables, R, C, N, E):
        rr = r[row_tot > 0][:I - 1]
        cc = c[col_tot > 0][:J - 1]
        ee = e[np.ix_(row_tot > 0, col_tot > 0)][:I - 1, :J - 1]
        oo = t[np.ix_(row_tot > 0, col_tot > 0)][:I - 1, :J - 1]
        s1 = s1 + (oo.reshape(dim, order='F') - ee.reshape(dim, order='F'))
        if n > 1:
            v = np.kron(n * np.diag(cc) - np.outer(cc, cc),
                        n * np.diag(rr) - np.outer(rr, rr)) / (n * n * (n - 1))
        else:
            v = np.zeros((dim, dim))
        s2 = s2 + v
    if np.linalg.matrix_rank(s2) != s2.shape[0]:
        return {'Q_GMH': None, 'degrees_of_freedom': dim, 'p_value': None}
    q = float(s1 @ np.linalg.solve(s2, s1))
    return {'Q_GMH': q, 'degrees_of_freedom': dim,
            'p_value': float(chi2.sf(q, dim))}


def build_strata(same1, diff1, same2, diff2):
    """Assemble the per-level 2x2 tables that `berry_mielke` expects.

    Each stratum is::

        [[same in population 1, different in population 1],
         [same in population 2, different in population 2]]
    """
    return [np.array([[s1, d1], [s2, d2]], dtype=float)
            for s1, d1, s2, d2 in zip(same1, diff1, same2, diff2)]


def paired_proportions(x, y, alpha=0.05):
    """Test and CI for the difference between two paired proportions.

    Port of the closing block of ``analyze_equality_2.m``: a McNemar-style
    z test on the discordant pairs plus the Newcombe (1998b) "method 10"
    confidence interval for the difference, which combines Wilson score
    bounds for each marginal proportion with an estimate of the association
    between them.

    `x` and `y` are 0/1 arrays of equal length (here: whether the equality
    test rejected in the sequential and in the simultaneous mode).
    """
    x = np.asarray(x).astype(int)
    y = np.asarray(y).astype(int)
    total = len(x)
    e = int(np.sum((x == 1) & (y == 1)))
    f = int(np.sum((x == 1) & (y == 0)))
    g = int(np.sum((x == 0) & (y == 1)))
    h = int(np.sum((x == 0) & (y == 0)))

    stat = (f - g) / np.sqrt(f + g) if (f + g) > 0 else np.nan
    p_value = 2 * norm.cdf(-abs(stat)) if np.isfinite(stat) else np.nan
    theta_hat = (f - g) / total

    if e * h <= f * g:
        num = e * h - f * g
    else:
        num = max(e * h - f * g - total / 2.0, 0.0)
    denom = np.sqrt((e + f) * (g + h) * (e + g) * (f + h))
    phi_hat = num / denom if denom > 0 else 0.0

    z = norm.ppf(1 - alpha / 2)

    def wilson(p):
        root = np.sqrt(4 * total * p * z ** 2 - 4 * total * p ** 2 * z ** 2 + z ** 4)
        lo = (2 * total * p + z ** 2 - root) / (2 * (total + z ** 2))
        hi = (2 * total * p + z ** 2 + root) / (2 * (total + z ** 2))
        return p - lo, hi - p

    dl2, du2 = wilson((e + f) / total)
    dl3, du3 = wilson((e + g) / total)
    delta = np.sqrt(dl2 ** 2 - 2 * phi_hat * dl2 * du3 + du3 ** 2)
    epsilon = np.sqrt(du2 ** 2 - 2 * phi_hat * du2 * dl3 + dl3 ** 2)

    return {
        'n': total, 'e': e, 'f': f, 'g': g, 'h': h,
        'p1': (e + f) / total, 'p2': (e + g) / total,
        'difference': theta_hat, 'z': stat, 'p_value': p_value,
        'phi_hat': phi_hat,
        'CI': (theta_hat - delta, theta_hat + epsilon),
    }
