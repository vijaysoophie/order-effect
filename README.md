# order-effect

Experiment code, data and analysis for a study of **order effects in luminance
discrimination**.

Observers judged whether a **test** luminance patch matched a **standard**
patch, in two experiments run on the same 21 people:

| Mode | Arrangement | Positions compared |
|---|---|---|
| **Sequential** | the two patches appear one after the other at the same location | test **first** vs test **second** |
| **Simultaneous** | the two patches appear side by side | test **left** vs test **right** |

The question is whether *when* or *where* the test appeared changes how bright
it looks (a **Type A** effect), how precisely it can be judged (a **Type B**
effect), and whether discrimination thresholds differ between the two modes.

Each observer completed four blocks per mode, one per standard luminance:
13.2, 26.4 and 39.5 cd/m², with the 26.4 cd/m² block run twice. Each block 
presented seven test luminances spaced logarithmically around the standard, 
48 trials each, half with the test in one position and half in the other.

## Repository layout

```
order-effect/
├── experiment/     Unity stimulus source, session harness, observer documents
├── data/           raw per-trial data for all 21 observers
└── analysis/       Python analysis notebooks and their results
```

Each folder has its own README with the details.

## Rebuilding the experiment

`experiment/unity-project/` holds the Unity source that presents the stimuli,
one project per mode, built with **Unity 6000.0.25f1**. Open the folder for
the mode you want in Unity Hub and build for your platform;
`experiment/README.md` explains the trial logic and where the published
timings live in the code. The compiled application itself is not committed —
see that README.

## Reproducing the analysis

```bash
cd analysis
pip install -r requirements.txt
jupyter lab
```

Run the four notebooks in numerical order. They read the raw data in `data/`
and write everything into `analysis/outputs/`, which is also committed here so
the results can be inspected without running anything. Total runtime is a few
minutes.

Each notebook ends with a verification section that compares its own output
against the original FORTRAN and MATLAB results of the same analyses. Those
checks pass as committed.

## Preregistration

The study design, sample size and primary analyses were preregistered before
data collection at **https://osf.io/nc34p**.

## Licence

Released under the MIT Licence — see [`LICENSE`](LICENSE). You are free to
use, modify and redistribute this material, including commercially, provided
the copyright notice is retained. If you use the data or the analysis in work
of your own, please also cite the accompanying paper.

## Contact

Vijay Singh — vsingh1@haverford.edu

The compiled stimulus program is not included in this repository (see
`experiment/README.md`). Please get in touch if you need it, or if the version
you obtain is not compatible with your system.
