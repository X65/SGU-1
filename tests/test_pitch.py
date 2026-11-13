import numpy as np
import pytest

from sgu_testkit import FREQ, frequency_word, represented_hz, estimate_frequency

pytestmark = pytest.mark.audio


@pytest.mark.parametrize("channel", range(9))
@pytest.mark.parametrize("operator", range(4))
@pytest.mark.parametrize("multiplier", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15])
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


@pytest.mark.known_defect(reason="Ratio multiplier truncates product before halving (sgu.c phase-step helper)")
def test_high_multiplier_preserves_pitch(chip, evidence):
    chip.tone(hz=1000, multiplier=15)
    audio = chip.render(24000)[2000:, 0]
    expected = represented_hz(frequency_word(1000)) * 15
    measured = estimate_frequency(audio)
    evidence.update(expected_hz=expected, measured_hz=measured)
    assert measured == pytest.approx(expected, abs=1)


@pytest.mark.parametrize("multiplier", [11, 13, 14])
@pytest.mark.known_defect(reason="README promises linear MUL=1..15, core uses OPL aliases for 11/13/14")
def test_documented_multiplier_ratios(chip, evidence, multiplier):
    chip.tone(multiplier=multiplier)
    expected = represented_hz(frequency_word(440)) * multiplier
    measured = estimate_frequency(chip.render(24000)[2000:, 0])
    evidence.update(expected_hz=expected, measured_hz=measured)
    assert measured == pytest.approx(expected, abs=0.05)
