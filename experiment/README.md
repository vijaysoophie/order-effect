# experiment

Everything needed to run the two experiments: the Unity source that presents
the stimuli, the Python harness that drives a session, and the documents given
to observers.

```
experiment/
├── unity-project/
│   ├── sequential/      Unity source, sequential mode
│   └── simultaneous/    Unity source, simultaneous mode
├── sequential/          launcher and condition generator
├── simultaneous/        the same, for the other mode
└── documents/           protocol and observer instructions
```

## `unity-project/` — the stimulus program

The source for the application that presents the stimuli and records
responses. Built with **Unity 6000.0.25f1**; open it with that version, as
Unity projects do not open cleanly across major releases.

Only the three directories Unity needs are committed — `Assets/`,
`Packages/` and `ProjectSettings/`. `Library/`, `Temp/`, `Logs/`,
`UserSettings/` and the solution files are regenerated on first open and are
excluded by `.gitignore`. The `.meta` files **are** committed and must stay:
they carry the GUIDs that bind the scripts to objects in the scene.

To rebuild: open the folder for the mode you want in Unity Hub, let it import,
open `Assets/Scenes/SampleScene.unity`, and build for your platform.

### The experiment script

`Assets/PsychophysicsExperiment.cs` is the file that matters. It reads a trial
list, presents the patches, collects the gamepad response and appends one line
per trial to the output file. The two modes differ in this script:

| | sequential | simultaneous |
|---|---|---|
| scene objects | one `square`, one `background` | `square1`/`square2`, `background1`/`background2` |
| presentation | `ShowStimulus(1)` → wait → black screen → wait → `ShowStimulus(2)` → wait | `ShowTrial()` once, left untimed |

Timing is declared at the top of the sequential script and matches the
published method:

```csharp
public float trialDuration = 0.300f;   // exposure per stimulus
public float ISI          = 0.600f;    // inter-stimulus interval
public float ITI          = 0.600f;    // inter-trial interval
```

Two points a reader reproducing this should know:

- Intervals are implemented with `WaitForSeconds`, which resumes on the first
  frame *after* the interval has elapsed. Exposure durations are therefore
  quantised to the display's frame period and may overshoot the nominal value
  by up to one frame.
- In the **simultaneous** script a `trialDuration` of 0.5 s is declared but the
  wait that would use it is commented out, so the pair stays on screen until
  the observer responds. This is deliberate and is what the paper reports; the
  unused declaration should not be read as a 0.5 s exposure.

`Assets/Scripts/test.cs` and `test1.cs` are small development stubs and play no
part in data collection.

## `sequential/` and `simultaneous/` — the Python harness

### `generate_conditions_for_subject.py`

Generates the trial list for every condition before an observer is run. For
each condition it takes the standard RGB triplet, the seven test triplets and
the background, and writes one line per trial giving the two patches, their
backgrounds, a trial order number, the position of the standard and the
expected response. Each list is written twice: in linear RGB and
gamma-corrected for the display.

Within a condition the standard appears in the first interval (or on the left)
on half the trials and in the second (or on the right) on the other half, with
the seven test levels crossed with both positions.

### `RunExperiment.py`

Drives a whole session. It generates a random condition order for the
observer — practice block first, `condition_0` second, then conditions 1–3
shuffled — saves it to `sequence.txt`, launches the Unity application once per
condition, and collects responses into the observer's data folder.

```bash
python RunExperiment.py <subject_name> [--base-folder PATH]
```

The **base folder** is the directory holding `Utilities/` (with the compiled
application), `Condition/` and `Data/`. It is resolved in this order:

1. the `--base-folder` option,
2. the `ORDER_EFFECT_BASE` environment variable,
3. the directory containing the script.

So no editing is needed: run it from a checkout and it works, or point it
elsewhere with the option. The script prints the base folder it resolved
before doing anything.

The two copies of `RunExperiment.py` are byte-identical; the two copies of
`generate_conditions_for_subject.py` differ only in an unused `import math`
and in commented-out code.

`generate_conditions_for_subject.py` takes the same `--base-folder` option,
plus `--subject` and `--gamma-file` (the display calibration exponents, which
are specific to the monitor in use):

```bash
python generate_conditions_for_subject.py \
    --subject <name> --gamma-file <calibration.txt> [--base-folder PATH]
```

## Compiled application

The built `Experiment1.app` bundles (79 MB each) are not committed. A signed
`.app` downloaded inside a zip archive generally will not launch on macOS
without being re-signed, and the source above is the more useful artefact in
any case. Please contact **vsingh1@haverford.edu** for a build, or if the copy
you obtain is not compatible with your system.

## `documents/`

| File | Contents |
|---|---|
| `OrderEffect_version2.pdf` | the experimental protocol |
| `Trial_Instructions_sequential.docx` | what observers were told, sequential mode |
| `Trial_Instructions_simultaneous.docx` | the same, simultaneous mode |

The protocol was byte-identical in the two source folders and is stored once.
The trial instructions differ between modes and are kept separately.

## Apparatus

Stimuli were presented on a colour-calibrated Dell UltraSharp 27 4K USB-C Hub
monitor, driven by an Apple iMac (macOS Sequoia 15.5, 3.3 GHz 6-core Intel
i5). Responses were collected with a Logitech Gamepad F310. Observers viewed
the display binocularly from 120 cm with the head held by a chin cup and
forehead rest (Headspot; UHCOTech). The room was dark apart from the monitor
and the walls were matte black. The monitor was calibrated with a Calibrite
DisplayPlus HL colorimeter driven through ArgyllCMS.
