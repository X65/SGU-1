import numpy as np
import pytest

from sgu_testkit import (
    FREQ, SAMPLE_RATE, frequency_word, represented_hz, estimate_frequency,
    estimate_spectral_peak,
)

pytestmark = pytest.mark.audio


@pytest.mark.parametrize("channel", range(9))
@pytest.mark.parametrize("operator", range(4))
@pytest.mark.parametrize("multiplier", range(16))
def test_operator_pitch(chip, evidence, channel, operator, multiplier):
    chip.tone(channel=channel, operator=operator, multiplier=multiplier)
    audio = chip.render(24000, channel)[2000:, 0]
    expected = represented_hz(frequency_word(440)) * (multiplier or 0.5)
    measured = estimate_frequency(audio)
    evidence.update(expected_hz=expected, measured_hz=measured)
    assert measured == pytest.approx(expected, abs=0.05)


@pytest.mark.parametrize("hz", [27.5, 55, 110, 220, 880, 1760, 3520])
def test_pitch_range(chip, hz):
    chip.tone(hz=hz)
    audio = chip.render(48000)[4000:, 0]
    assert estimate_frequency(audio) == pytest.approx(
        represented_hz(frequency_word(hz)), abs=0.05)


@pytest.mark.parametrize("operator", range(4))
@pytest.mark.parametrize("mul,scale", [(0, 7), (7, 5), (15, 7)])
def test_fixed_frequency_ignores_channel_pitch(chip, operator, mul, scale):
    chip.tone(operator=operator, multiplier=mul, fixed=True, detune=scale)
    first = chip.render(48000)[4000:, 0]
    chip.word(0, FREQ, frequency_word(1760))
    second = chip.render(48000)[:, 0]
    word = (8 + (mul * 247 + 7) // 15) << scale
    for audio in (first, second):
        assert estimate_frequency(audio) == pytest.approx(represented_hz(word), abs=0.05)


def test_four_carriers_sum(chip):
    chip.tone(volume=16)
    single = chip.render(12000)[2000:, 0]
    chip.reset()
    for operator in range(4):
        chip.tone(operator=operator, volume=16)
    combined = chip.render(12000)[2000:, 0]
    # Integer rounding in channel gain and final DC filtering permits a few LSBs.
    np.testing.assert_allclose(combined, single.astype(float) * 4, atol=8, rtol=0)
    assert estimate_frequency(combined) == pytest.approx(
        represented_hz(frequency_word(440)), abs=0.05)


def test_high_sine_pitch(chip, evidence):
    chip.tone(hz=1000, multiplier=15)
    audio = chip.render(50000)[2000:, 0]
    expected = represented_hz(frequency_word(1000)) * 15
    # High-frequency sine output is shaped by BLEP; count the spectral peak
    # instead of assuming every cycle has exactly one rising zero crossing.
    measured = estimate_spectral_peak(audio)
    evidence.update(expected_hz=expected, measured_hz=measured)
    assert measured == pytest.approx(expected, abs=0.5)


@pytest.mark.parametrize("operator", range(4))
@pytest.mark.parametrize("hz,multiplier", [
    (1000, 15), (1599, 15), (1601, 15), (3000, 10),
    (3000, 15), (3201, 15), (3900, 15),
])
def test_high_multiplier_preserves_pitch(chip, evidence, operator, hz, multiplier):
    # A sampled sine bypasses BLEP's high-frequency waveshaping, isolating
    # oscillator pitch while still checking the rendered audio path.
    chip.pcm(np.rint(127 * np.sin(2 * np.pi * np.arange(1024) / 1024)))
    chip.tone(hz=hz, operator=operator, multiplier=multiplier, wave=7)
    frequency = represented_hz(frequency_word(hz)) * multiplier
    expected = abs((frequency + SAMPLE_RATE / 2) % SAMPLE_RATE - SAMPLE_RATE / 2)
    measured = estimate_spectral_peak(chip.render(50000)[2000:, 0])
    evidence.update(expected_hz=expected, measured_hz=measured)
    assert measured == pytest.approx(expected, abs=0.5)


@pytest.mark.parametrize("operator", range(4))
@pytest.mark.parametrize("multiplier", range(16))
def test_phase_step_at_multiplier_boundaries(chip, operator, multiplier):
    ratio = multiplier or 0.5
    words = {0, 1, frequency_word(440), 65535}
    # Exercise both sides of the old doubled-product overflow and the normal
    # full-cycle phase wrap. Expectations come from Hz, not the core helper.
    for frequency in (SAMPLE_RATE / 2, SAMPLE_RATE):
        boundary = round(frequency / ratio * 2**24 / 1_000_000)
        words.update(word for word in range(boundary - 1, boundary + 2)
                     if 0 <= word <= 65535)
    for word in sorted(words):
        chip.reset()
        chip.tone(operator=operator, multiplier=multiplier)
        chip.word(0, FREQ, word)
        chip.render(1)
        before = chip.lib.test_phase(chip.handle, 0, operator)
        chip.render(1)
        after = chip.lib.test_phase(chip.handle, 0, operator)
        measured = (after - before) % 2**32
        expected = represented_hz(word) * ratio / SAMPLE_RATE * 2**32
        error = (measured - expected + 2**31) % 2**32 - 2**31
        # Base-step rounding, amplified by at most x15, costs <= 8 phase LSBs.
        assert abs(error) <= 8, (word, multiplier, measured, expected)
