# SGU-1 functional and audio tests

The suite runs the real `sgu.c` through a compiled CFFI adapter. Pytest owns
collection, fixtures, parameterization and reporting; NumPy/SciPy perform signal
measurements. Hypothesis generates register-write cases. Pytest-regressions owns
numerical baselines. No synthesis code is reimplemented in Python.

## Run

Requires Python 3.11 or newer, its development headers, and GCC or Clang.
The local validation and CI configuration use Python 3.14 on Linux.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/pytest --html=test-results/report.html --junitxml=test-results/junit.xml
```

The native adapter builds once per pytest session in pytest's temporary directory.
Select a compiler with `CC=clang` or `CC=gcc`. The core is compiled as C, not C++.
The core's own GCC `optimize("Ofast")` attributes still apply; the test build does
not remove them or claim sanitizer coverage.

Useful selections:

```sh
.venv/bin/pytest tests/test_pitch.py
.venv/bin/pytest -m audio
.venv/bin/pytest -m regression
.venv/bin/pytest -k pcm
.venv/bin/pytest -m known_defect --run-known-defects
.venv/bin/pytest -k sine_has --audio-artifacts=all --html=test-results/report.html
```

`--run-known-defects` makes known problems ordinary failures. Normally these tests
are **strict xfails**: they execute on every run and an unexpected pass fails the
suite, prompting removal of the marker. They are not approved golden behavior.

## Coverage and limits

- 440 Hz across all nine channels and four operators, with MUL 0 (half rate),
  1–10, 12 and 15. MUL 11/13/14 each have separate specification discrepancy tests.
- Low/high notes, fixed-frequency mode, channel pitch independence, and four-carrier
  mixing. Pitch expectations include register quantization and use the documented
  SID relationship: `frequency_word * 1,000,000 / 2^24`.
- Reset silence/replay, seeded noise replay, stereo pan endpoints, clip flags,
  self-clearing requests, volume sweep bounds, register isolation, exact PCM
  sequencing/loops and gate pause/resume.
- Single versus split rendering at every channel partition. This is a sequential
  equivalence check with channel ring modulation disabled, not a concurrency test.
- Buffer-size independence with register writes at exact sample indices.
- Sine ticks, residual distortion, high-frequency noise, attenuation, quiet notes,
  release tails, filter impulse decay, seamless PCM looping, and harmonic baselines.
- Measurement calibration using analytical tones and injected impulses, dropped
  samples, broken loops and seeded white noise.

These are controlled signal tests, not a general perceptual quality score. The
crossing-based frequency estimator is for isolated clean sines; it is not a pitch
tracker for arbitrary FM patches. The local tick detector is for smooth signals,
not intentional pulse/sync/ring-modulation discontinuities. Essentia is not required
or integrated yet. MCU deadlines, concurrent bus writes, analog noise, full envelope
rate tables, modulation sideband matrices and comprehensive aliasing sweeps remain
future coverage.

## Measurement contracts

Audio uses 48 kHz. Full scale is **65536 core units**, matching the hardware's
`ssat16(mix >> 1)` conversion. Neither measurements nor WAVs are peak-normalized.

| Check | Initial acceptance criterion |
| --- | --- |
| Isolated pitch | Within 0.05 Hz of the encoded frequency |
| Fresh reset | Every output sample exactly zero |
| Settled sine | No midpoint prediction error above 64 core units |
| Sine residual after fitted fundamental/DC removal | Below -70 dBFS RMS |
| Sine 8–20 kHz noise/distortion band | Below -75 dBFS integrated power |
| TL gain | Within 0.35 dB of the specified 0.75 dB steps |
| Quiet sine (TL=48) | Signal above -65 dBFS; residual below -90 dBFS |
| Released tail | At most one output LSB; 8–20 kHz below -100 dBFS |
| Low-cutoff filter tail | No oscillation above one count peak-to-peak; bounded DC residue |

These are explicit initial engineering budgets, not claims of inaudibility. The
sine noise band includes harmonic/LUT error, so it is not exclusively stochastic
hiss. Welch analysis disables automatic DC removal. Filter integrators can retain
DC below one integer update: the low-cutoff test permits `ceil(65536/(3*cutoff))+1`
counts internally, while separately checking variation and output-band energy.

## Failure artifacts

By default, failures and expected failures save a directory under `test-results/`:

- `raw.npy`: exact int32 columns **left, right, selected channel raw, selected
  channel post-filter**; preserves values beyond hardware clipping.
- `output.wav`: stereo 16-bit hardware-scaled audio, with hardware-style saturation.
- `analysis.png`: waveform, power spectrum and spectrogram of left output.
- `metrics.json`: sample rate, scale, render start, channel, register-write history,
  measured levels, and test-specific expected/measured values when provided.

The HTML report links these files and includes an audio player. Keep the whole
`test-results` directory when sharing or downloading CI artifacts; this is not a
self-contained HTML report. Each test captures its **last render block**, so a test
comparing multiple renders should ensure the failing candidate is rendered last.
`--audio-artifacts=all` saves passing cases too; `none` disables artifact generation.
Artifacts are diagnostic output, not committed regression data.

## Baselines

`test_audio/test_sine_spectral_regression.npz` contains eight harmonic amplitudes
relative to hardware full scale. It was captured from the initial core after the
independent pitch, residual, level and noise assertions passed. Fundamental
amplitude is about 0.061711; third harmonic about 0.0000919. This records the
existing LUT character, not an ideal sine. Tolerances are 2e-6 absolute plus 1%
relative. The independent assertions prevent a silent output or broadly degraded
sine from being accepted merely by updating the baseline.

To intentionally regenerate only that baseline:

```sh
.venv/bin/pytest -m regression --force-regen
.venv/bin/pytest -m regression
```

Review old/new numerical values and audio before accepting a changed baseline.
The plugin can report failure during regeneration; rerun to verify the result.
Never regenerate baselines automatically in CI. Add new acoustic baselines with
independent absolute limits and a documented reason for their tolerances.

## Known failures in the initial core

| Test | Current behavior |
| --- | --- |
| Documented MUL 11/13/14 | Core uses OPL aliases 10/12/15, whereas README says 1–15 are linear |
| High multiplier | 1000 Hz × 15 suffers phase-product truncation before halving |
| High-cutoff impulse | Filter does not settle at cutoff 0xFFFF, resonance zero |
| Reset replay at 110 Hz | BLEP/sample history survives reset and changes the next attack |

These six cases cover four issues. Resolve the specification choice for multiplier
aliases before deciding whether to change the core or the documentation/test.
No production source changes are part of this test-suite addition.
