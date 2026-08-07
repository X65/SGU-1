# SGU-1

**Sound Generator Unit 1** is an audio-synthesis hardware module under development as part of the [X65 Microcomputer Project](https://x65.zone/).

SGU-1 combines ideas from OPL/ESFM, OPM, SID, POKEY, and Paula in a new design built around four-operator FM synthesis, per-channel subtractive filtering, hardware modulation, and PCM sample playback. It is intended for modern retro computers, original vintage machines, and modern embedded systems.

> **Status:** Engineering prototype. Electrical limits, pin assignments, and production specifications are not yet released. Revision 1 data must not be used for production designs.

## Architecture

The module pairs a microcontroller with an audio CODEC. The synthesis engine produces a stereo 48 kHz I²S stream, which the CODEC converts to an analog stereo line-level output. The hardware uses a compact castellated-module format for board-level integration.

## Capabilities

- 9 channels of 4-operator FM synthesis
- Stereo 48 kHz audio output
- 8 waveforms per operator: sine, triangle, sawtooth, pulse, noise, periodic noise, reserved, and sample
- Per-operator waveform shaping through WPAR
- ESFM-style routing with independent output and modulation-input levels
- Per-operator hard sync and ring modulation
- OPN-style ADSR envelopes with sustain-rate control
- Level-driven GATE and one-shot TRIG controls
- Per-channel resonant low-pass, band-pass, and high-pass filters
- Continuous signed pulse width with 128 widths and two placements
- Per-channel volume, frequency, and cutoff sweep units
- Per-channel phase-reset timer
- Saw, square, triangle, and noise LFO shapes for AM and PM
- 64 KiB PCM sample memory

## Integration and development

Host software and target-side playback can be adapted to the target system. Current development control is available through SPI and USB MIDI.

[sgu-tracker](https://github.com/X65/sgu-tracker) and the 6502 SGM player are used as a development and proof-of-concept platform. They demonstrate one possible toolchain for instrument definition, sequencing, effect control, module export, and playback; they are not required components of the SGU-1 architecture.

## Documentation

- [SGU-1 product page](https://x65.zone/sgu-1/)
- [X65 memory map and register definitions](https://tinyurl.com/x65-memory-map)

Additional product, register, hardware, and software documentation is in development.

## Website

The product website is maintained as a self-contained static site on the [`gh-pages`](https://github.com/X65/sgu-1/tree/gh-pages) branch. It uses GitHub Pages' classic **Deploy from a branch** configuration and does not require a GitHub Actions workflow.
