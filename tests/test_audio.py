import numpy as np
import pytest
from sgu_testkit import (
    SAMPLE_RATE, FLAGS0, CUTOFF, RESON, FULL_SCALE, frequency_word,
    represented_hz, estimate_frequency, sine_residual, rms_dbfs, band_dbfs,
    tick_indices, estimate_spectral_peak,
)

pytestmark = pytest.mark.audio


def test_sine_has_no_unexpected_ticks_or_hiss(chip, evidence):
    chip.tone()
    audio = chip.render(48000)[4000:, 0]
    frequency = estimate_frequency(audio)
    residual = sine_residual(audio, frequency)
    evidence.update(residual_dbfs=rms_dbfs(residual), hiss_dbfs=band_dbfs(audio))
    assert not len(tick_indices(audio))
    assert rms_dbfs(residual) < -70
    assert band_dbfs(audio) < -75


@pytest.mark.parametrize("attenuation", [0, 16, 32, 48])
def test_attenuation_follows_db_steps(chip, attenuation):
    chip.tone(attenuation=0)
    reference = chip.render(24000)[4000:, 0]
    chip.reset()
    chip.tone(attenuation=attenuation)
    quiet = chip.render(24000)[4000:, 0]
    assert rms_dbfs(quiet) - rms_dbfs(reference) == pytest.approx(
        -0.75 * attenuation, abs=0.35)


def test_release_reaches_quiet_tail(chip, evidence):
    chip.tone()
    chip.render(4000)
    chip.write(0, FLAGS0, 0)
    tail = chip.render(96000)[-24000:, 0]
    evidence.update(tail_dbfs=rms_dbfs(tail))
    assert np.max(np.abs(tail)) <= 1
    assert band_dbfs(tail) < -100


@pytest.mark.parametrize("cutoff", [0x800, 0x1800, 0x2800])
def test_filter_impulse_decays(chip, cutoff):
    chip.pcm([100, 0])
    chip.word(0, 0x20, 0x8000)
    chip.word(0, 0x2C, 1)
    chip.write(0, 0x22, 64)
    chip.word(0, CUTOFF, cutoff)
    chip.write(0, RESON, 0)
    chip.write(0, FLAGS0, 0x29)
    samples = chip.render(48000)
    assert np.max(np.abs(samples[:100, 3])) > 10
    # Fixed-point integration can retain a small DC residue below one update.
    dc_budget = np.ceil(65536 / (3 * cutoff)) + 1
    tail = samples[-4000:, 3]
    assert np.max(np.abs(tail)) <= dc_budget
    assert np.ptp(tail) <= 1
    assert band_dbfs(samples[-4000:, 0]) < -90


def test_filter_recovers_after_restoring_cutoff(chip):
    chip.pcm([100, 0])
    chip.word(0, 0x20, 0x8000)
    chip.word(0, 0x2C, 1)
    chip.write(0, 0x22, 64)
    chip.word(0, CUTOFF, 0xFFFF)
    chip.write(0, FLAGS0, 0x29)
    chip.render(4096)
    chip.word(0, CUTOFF, 0x4000)
    samples = chip.render(48000)
    assert np.max(np.abs(samples[-4000:, 3])) <= 8


def test_seamless_pcm_loop_has_no_extra_tick(chip):
    pcm = np.rint(100 * np.sin(2 * np.pi * np.arange(256) / 256)).astype(np.int8)
    chip.pcm(pcm)
    chip.word(0, 0x20, 0x8000)
    chip.word(0, 0x2C, 256)
    chip.write(0, 0x22, 64)
    chip.write(0, FLAGS0, 9)
    chip.write(0, 0x25, 4)
    audio = chip.render(8192)[:, 2]
    np.testing.assert_array_equal(audio, np.tile(pcm.astype(np.int32) * 64, 32))
    assert not len(tick_indices(audio, threshold=65))


@pytest.mark.regression
def test_sine_spectral_regression(chip, ndarrays_regression):
    chip.tone()
    audio = chip.render(24000)[4000:, 0]
    hz = represented_hz(frequency_word(440))
    t = np.arange(len(audio)) / SAMPLE_RATE
    # Project onto known harmonics. Store compact metrics, not plot pixels.
    harmonics = np.arange(1, 9)
    basis = np.column_stack([np.ones(len(t))] + [
        wave(2 * np.pi * hz * harmonic * t)
        for harmonic in harmonics for wave in (np.sin, np.cos)
    ])
    coefficients = np.linalg.lstsq(basis, audio, rcond=None)[0][1:].reshape(-1, 2)
    amplitudes = np.linalg.norm(coefficients, axis=1) / FULL_SCALE
    ndarrays_regression.check({"harmonic_amplitudes": amplitudes},
                              default_tolerance={"atol": 2e-6, "rtol": 0.01})


@pytest.mark.parametrize("hz", [27.5, 440, 6600])
def test_frequency_measurement_calibration(hz):
    t = np.arange(48000) / SAMPLE_RATE
    x = 3000 * np.sin(2 * np.pi * hz * t + 0.73)
    assert estimate_frequency(x) == pytest.approx(hz, abs=0.01)


@pytest.mark.parametrize("hz", [27.5, 440.13, 14999.81, 23984.7])
def test_spectral_pitch_measurement_calibration(hz):
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    x = 100 + 3000 * np.sin(2 * np.pi * hz * t + 0.73)
    assert estimate_spectral_peak(x) == pytest.approx(hz, abs=0.5)


def test_tick_detector_detects_injected_impulse():
    x = 4000 * np.sin(2 * np.pi * 440 * np.arange(48000) / SAMPLE_RATE)
    assert not len(tick_indices(x))
    x[12345] += 1000
    assert 12345 in tick_indices(x)


def test_hiss_measurement_detects_injected_noise():
    x = 4000 * np.sin(2 * np.pi * 440 * np.arange(48000) / SAMPLE_RATE)
    noisy = x + np.random.default_rng(42).normal(0, 20, len(x))
    assert band_dbfs(x) < -100
    assert band_dbfs(noisy) > -80


def test_tick_detector_detects_broken_loop():
    period = 4000 * np.sin(2 * np.pi * np.arange(256) / 256)
    clean = np.tile(period, 8)
    broken = np.tile(period[:200], 8)
    assert not len(tick_indices(clean))
    assert any(abs(tick_indices(broken) - 200) <= 1)


def test_tick_detector_detects_dropped_sample():
    x = 4000 * np.sin(2 * np.pi * 440 * np.arange(48000) / SAMPLE_RATE)
    damaged = np.delete(x, 12000)
    assert any(abs(tick_indices(damaged) - 12000) <= 1)


def test_quiet_sine_remains_detectable_above_noise(chip, evidence):
    chip.tone(attenuation=48)
    audio = chip.render(48000)[4000:, 0]
    expected = represented_hz(frequency_word(440))
    residual = sine_residual(audio, expected)
    evidence.update(signal_dbfs=rms_dbfs(audio), residual_dbfs=rms_dbfs(residual))
    assert rms_dbfs(audio) > -65  # A silent/broken voice must not pass a noise test.
    assert rms_dbfs(residual) < -90
