# data

Raw per-trial data for all 21 observers, in both modes of presentation.

```
data/
├── sequential/      one folder per observer + Completed Participants
└── simultaneous/    the same
```

Observers are identified by nickname only. Every folder here belongs to an 
observer whose data are analysed in the paper. 
`Completed Participants` lists those 21 observers.

## Inside an observer's folder

```
<Observer>/
├── sequence.txt                 the order in which conditions were run
├── progress.txt                 how far the session got
├── condition_demo/              practice block, not analysed
├── condition_0/ … condition_3/
└── …
    └── Repetition_1/
        ├── <Observer>_condition_<k>_Repetition_1.txt   the responses
        ├── conditions_condition_<k>_rep_1.txt          parameters used
        ├── trials_condition_<k>_rep_1.txt              trial list, linear RGB
        └── trials_condition_<k>_rep_1_gamma_corrected.txt
```

### Conditions

| Folder | Standard | Note |
|---|---|---|
| `condition_demo` | 26.4 cd/m² | practice, 84 trials, 12 per test level; **not analysed** |
| `condition_0` | 26.4 cd/m² | always administered first |
| `condition_1` | 13.2 cd/m² | |
| `condition_2` | 26.4 cd/m² | a repeat of condition 0, run later |
| `condition_3` | 39.5 cd/m² | |

Conditions 0 and 2 are identical in design. Comparing them measures how much
performance drifted over the course of data collection; the paper reports that
it drifted appreciably.

### The response file

`<Observer>_condition_<k>_Repetition_1.txt` is the file the analysis reads.
One line per trial, comma-separated:

```
129, 1, 2, 1, RGBA(60, 60, 60, 255), RGBA(0, 0, 0, 160), RGBA(52, 52, 52, 255), RGBA(0, 0, 0, 160)
```

| Field | Meaning |
|---|---|
| 1 | trial order number |
| 2 | interval or side holding the **standard** (1 or 2) |
| 3 | the objectively correct response |
| 4 | the observer's response: **1 = "same"**, **2 = "different"** |
| 5–6 | RGBA of the patch in position 1, then its background |
| 7–8 | RGBA of the patch in position 2, then its background |

All patches are achromatic, so R = G = B and a single number describes each
one. Note that field 2 gives the position of the *standard*; the analysis is
organised around the position of the *test*, which is simply `3 − field 2`.

Responses other than 1 or 2 mean no valid response was recorded and are
dropped by the analysis.

### Grey level to luminance

The experiment specified patches by 8-bit grey level; the analysis works in
measured luminance. The mapping, measured for the levels actually used:

| grey | 20 | 23 | 26 | 30 | 34 | 40 | 45 | 52 | 59 | 60 | 68 | 69 | 78 | 79 | 90 | 91 | 103 | 119 | 136 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cd/m² | 8.8 | 10.1 | 11.4 | 13.2 | 14.9 | 17.6 | 19.8 | 22.4 | 25.9 | 26.4 | 29.9 | 30.3 | 34.3 | 34.7 | 39.5 | 39.96 | 45.2 | 52.3 | 59.7 |

This table is also in `analysis/orderfx.py` as `LOOKUP`.

### ⚠ A note on capitalisation

Capitalisation is **not consistent** in this tree, and it does not merely vary
between folders — a folder and the files inside it can disagree:

| Mode | Folder | Prefix on the files inside |
|---|---|---|
| sequential | `kir` | `Kir_…` (all four conditions) |
| sequential | `mac` | `Mac_…` (conditions 2 and 3) |
| sequential | `ness` | `Ness_…` (conditions 0 and 2) |
| simultaneous | `Kir` | `kir_…` (all four conditions) |

macOS and Windows filesystems are case-insensitive and hide this entirely. On
Linux — and therefore on most CI runners — code that builds a filename from
the folder name will fail to find those files and will **silently analyse
fewer observers** rather than raise an error.

The Python analysis here resolves both folder and file names
case-insensitively (`_find_entry` and `_find_response_file` in
`analysis/orderfx.py`) and so is unaffected. Anyone writing their own reader
should do the same, and should assert that all 21 observers were found.
