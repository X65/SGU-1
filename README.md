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

Listen to the [SGU-1 playing other chips](https://www.youtube.com/playlist?list=PLbSCQdOP-_xh-mkkLIiCdmu_ArqHcOkYM) playlist for demonstrations of SGU-1 reproducing music written for other sound chips.

## Documentation

- [SGU-1 product page](https://x65.zone/sgu-1/)
- [X65 memory map and register definitions](https://tinyurl.com/x65-memory-map)

### SGU-1 register map

The CPU-visible SGU-1 window occupies `$FEC0`–`$FEFF`. Registers `$FEC0`–`$FEFE`
access the channel selected by `CHANNEL_SELECT`; multi-byte values are little-endian
(`LO` followed by `HI`).

Each channel has four operators with the same eight-register layout. The table below
describes Operator 0 at `$FEC0`–`$FEC7`; Operators 1–3 mirror its R0–R7 layout.

| Address | Register | Bit layout / value | Description |
| --- | --- | --- | --- |
| `$FEC0` | `OP0_R0` | `[7] TRM`, `[6] VIB`, `[5:4] KSR`, `[3:0] MUL` | Operator tremolo/vibrato enables, 2-bit key scaling, and frequency multiplier (`0` = 0.5x; `1`–`15` = 1x–15x). |
| `$FEC1` | `OP0_R1` | `[7:6] KSL`, `[5:0] TL_lo6` | Key-scale level and low six bits of 7-bit total attenuation (0.75 dB steps); `TL_msb` is in R6. |
| `$FEC2` | `OP0_R2` | `[7:4] AR_lo4`, `[3:0] DR_lo4` | Low four bits of the attack and decay rates; their MSBs are in R7. |
| `$FEC3` | `OP0_R3` | `[7:4] SL`, `[3:0] RR` | Sustain level and release rate. |
| `$FEC4` | `OP0_R4` | `[7:5] DT`, `[4:0] SR` | Detune and sustain rate. In fixed-frequency mode, `DT` selects the frequency scale instead. |
| `$FEC5` | `OP0_R5` | `[7:5] DELAY`, `[4] FIX`, `[3:0] WPAR` | Key-on delay of `2^(DELAY+8)` samples, fixed-frequency mode, and waveform-dependent shaping. |
| `$FEC6` | `OP0_R6` | `[7] TRMD`, `[6] VIBD`, `[5] SYNC`, `[4] RING`, `[3:1] MOD`, `[0] TL_msb` | LFO depths, hard sync, operator ring modulation, modulation depth (6 dB steps), and total-level MSB. On Operator 0, `MOD` controls feedback. |
| `$FEC7` | `OP0_R7` | `[7:5] OUT`, `[4] AR_msb`, `[3] DR_msb`, `[2:0] WAVE` | Direct output level (6 dB steps), rate MSBs, and waveform: `0` sine, `1` triangle, `2` sawtooth, `3` pulse, `4` noise, `5` periodic noise, `6` reserved, `7` PCM sample. |
| `$FEC8`–`$FECF` | `OP1_R0`–`OP1_R7` | Same as Operator 0 R0–R7 | Operator 1 mirrors `$FEC0`–`$FEC7` at an offset of `$08`. |
| `$FED0`–`$FED7` | `OP2_R0`–`OP2_R7` | Same as Operator 0 R0–R7 | Operator 2 mirrors `$FEC0`–`$FEC7` at an offset of `$10`. |
| `$FED8`–`$FEDF` | `OP3_R0`–`OP3_R7` | Same as Operator 0 R0–R7 | Operator 3 mirrors `$FEC0`–`$FEC7` at an offset of `$18`. |
| `$FEE0` | `FREQ_LO` | Frequency `[7:0]` | Low byte of the 16-bit channel phase increment or PCM playback rate. |
| `$FEE1` | `FREQ_HI` | Frequency `[15:8]` | High byte of the 16-bit channel phase increment or PCM playback rate. |
| `$FEE2` | `VOL` | Signed 8-bit | Channel volume; negative values invert the output amplitude. |
| `$FEE3` | `PAN` | Signed 8-bit | Stereo position; negative pans left and positive pans right. |
| `$FEE4` | `FLAGS0` | `[7] NSBAND`, `[6] NSHIGH`, `[5] NSLOW`, `[4] RING_MOD`, `[3] PCM`, `[2] reserved`, `[1] TRIG`, `[0] GATE` | Channel control. `TRIG` is a self-clearing hard retrigger; `GATE` is level-driven. The filter bits independently select band-, high-, and low-pass output. |
| `$FEE5` | `FLAGS1` | `[7] DIAG`, `[6] CUT_SWEEP`, `[5] VOL_SWEEP`, `[4] FREQ_SWEEP`, `[3] TIMER_SYNC`, `[2] PCM_LOOP`, `[1] FILTER_PHASE_RESET`, `[0] PHASE_RESET` | Sweep and PCM-loop enables plus timer sync. Both phase-reset bits are one-shot requests. `DIAG` switches the channel's readback to diagnostic mode (see below). |
| `$FEE6` | `CUTOFF_LO` | Cutoff `[7:0]` | Low byte of the 16-bit filter cutoff control. |
| `$FEE7` | `CUTOFF_HI` | Cutoff `[15:8]` | High byte of the 16-bit filter cutoff control. |
| `$FEE8` | `DUTY` | Signed 8-bit | Pulse width and placement. The magnitude is the low-run length; the sign places it at the beginning or end of the period. |
| `$FEE9` | `RESON` | Unsigned 8-bit | Filter resonance amount (`0`–`255`). |
| `$FEEA` | `PCMPOS_LO` | PCM position `[7:0]` | Low byte of the current PCM sample position. |
| `$FEEB` | `PCMPOS_HI` | PCM position `[15:8]` | High byte of the current PCM sample position. |
| `$FEEC` | `PCMBND_LO` | PCM boundary `[7:0]` | Low byte of the PCM boundary/end position. |
| `$FEED` | `PCMBND_HI` | PCM boundary `[15:8]` | High byte of the PCM boundary/end position. |
| `$FEEE` | `PCMRST_LO` | PCM restart `[7:0]` | Low byte of the PCM loop restart position; also the base address for the operator sample waveform. |
| `$FEEF` | `PCMRST_HI` | PCM restart `[15:8]` | High byte of the PCM loop restart position. |
| `$FEF0` | `SWFREQ_SPEED_LO` | Speed `[7:0]` | Low byte of samples between frequency-sweep steps; zero disables the sweep. |
| `$FEF1` | `SWFREQ_SPEED_HI` | Speed `[15:8]` | High byte of samples between frequency-sweep steps. |
| `$FEF2` | `SWFREQ_AMT` | `[7] DIR`, `[6:0] STEP` | Exponential frequency-sweep direction (`1` = up) and step size. |
| `$FEF3` | `SWFREQ_BOUND` | Unsigned 8-bit | Coarse frequency target; the sweep saturates at `BOUND << 8`. |
| `$FEF4` | `SWVOL_SPEED_LO` | Speed `[7:0]` | Low byte of samples between volume-sweep steps; zero disables the sweep. |
| `$FEF5` | `SWVOL_SPEED_HI` | Speed `[15:8]` | High byte of samples between volume-sweep steps. |
| `$FEF6` | `SWVOL_AMT` | `[7] BOUNCE`, `[6] LOOP`, `[5] DIR`, `[4:0] STEP` | Linear signed volume-sweep mode, direction (`1` = up), and step size. |
| `$FEF7` | `SWVOL_BOUND` | Signed 8-bit | Volume target and segment boundary; used by one-shot, repeat, and ping-pong modes. |
| `$FEF8` | `SWCUT_SPEED_LO` | Speed `[7:0]` | Low byte of samples between cutoff-sweep steps; zero disables the sweep. |
| `$FEF9` | `SWCUT_SPEED_HI` | Speed `[15:8]` | High byte of samples between cutoff-sweep steps. |
| `$FEFA` | `SWCUT_AMT` | `[7] DIR`, `[6:0] STEP` | Cutoff-sweep direction (`1` = up) and step size; upward sweeps are linear and downward sweeps are exponential. |
| `$FEFB` | `SWCUT_BOUND` | Unsigned 8-bit | Coarse cutoff target; the sweep saturates at `BOUND << 8`. |
| `$FEFC` | `RESTIMER_LO` | Reset period `[7:0]` | Low byte of the periodic phase-reset interval used when `TIMER_SYNC` is enabled. |
| `$FEFD` | `RESTIMER_HI` | Reset period `[15:8]` | High byte of the periodic phase-reset interval. |
| `$FEFE` | `LFOW` | `[7:4] reserved`, `[3:2] PM_SHAPE`, `[1:0] AM_SHAPE` | AM and PM LFO shapes: `0` saw, `1` square, `2` triangle, `3` noise. |
| `$FEFF` | `CHANNEL_SELECT` (`SPECIAL`) | Channel number | Selects the channel exposed through the register window. Values `$00`–`$08` select the nine synthesis channels; `$FF` maps implementation-specific service registers. |

### Diagnostic mode (`FLAGS1` bit 7)

Setting `DIAG` on a channel makes designated offsets of that channel's 64-byte
window dual-function: writes still land in the register file as usual, reads
return live chip state. Everything not listed (and everything while `DIAG` is
clear) reads the register file. All values are pre-`VOL`, pre-pan.

| window offset | diag read |
| --- | --- |
| op *n* base+0 | envelope attenuation, 0.375 dB steps (0 = full level, 255 = silent) |
| op *n* base+1 | EG state in bits 1:0 (attack/decay/sustain/release), bit 2 = TRIG-armed key-on DELAY window active |
| op *n* base+2/+3 | operator sample lo/hi (current operator value, `int16`) |
| `$FEE0/$FEE1` (`FREQ` slots) | channel sample lo/hi: the raw channel mix, `int16`, pre-`VOL`/filter/pan; live for PCM channels too |
| `$FEE2` (`VOL` slot) | channel envelope, 0..255 linear (`SGU_GetEnvelope >> 5`); 0 for a PCM-mode channel |

Sample lo/hi come from two separate bus reads while rendering runs at 48 kHz, so
a pair can straddle a sample boundary -- jitter, not corruption.

Additional product, register, hardware, and software documentation is in development.

## Website

The product website is maintained as a self-contained static site on the [`gh-pages`](https://github.com/X65/sgu-1/tree/gh-pages) branch. It uses GitHub Pages' classic **Deploy from a branch** configuration and does not require a GitHub Actions workflow.
