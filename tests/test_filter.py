"""Recovery from extreme settings without changing the filter transfer function."""
import numpy as np
import pytest

from sgu_testkit import Chip, CUTOFF, RESON, FLAGS0, FREQ, VOL

pytestmark = pytest.mark.audio

# Include stable high-resonance settings above the rejected fixed cutoff cap.
STABLE_SETTINGS = [(cutoff, resonance)
                   for cutoff in [0x800, 0x2800, 0x4000, 0x6000]
                   for resonance in [0, 128, 224, 255]] + [
                       (0x8000, 128), (0x8000, 224), (0x8000, 255), (0xA000, 255)]


@pytest.mark.parametrize("cutoff,resonance", STABLE_SETTINGS)
@pytest.mark.parametrize("excursion_resonance", [0, 255])
@pytest.mark.parametrize("mode", [0x20, 0x40, 0x80, 0xE0], ids=["lp", "hp", "bp", "all"])
def test_filter_recovers_after_extreme_settings(
        chip, native, evidence, cutoff, resonance, excursion_resonance, mode):
    reference = Chip(*native, {})
    try:
        for instance in [reference, chip]:
            instance.tone(volume=16)
            instance.word(0, CUTOFF, cutoff)
            instance.write(0, RESON, resonance)
            instance.write(0, FLAGS0, mode | 1)
            instance.render(4000)
        reference.render(4096 + 96000)
        expected = reference.render(4000)[:, 3].astype(float)

        chip.word(0, CUTOFF, 0xFFFF)
        chip.write(0, RESON, excursion_resonance)
        chip.render(4096)  # Extreme behavior is permitted here.
        chip.word(0, CUTOFF, cutoff)
        chip.write(0, RESON, resonance)
        chip.render(96000)
        recovered = chip.render(4000)[:, 3].astype(float)
        error_rms = float(np.sqrt(np.mean((recovered - expected)**2)))
        evidence.update(recovery_error_rms=error_rms,
                        recovered_dc=float(recovered.mean()),
                        reference_dc=float(expected.mean()))
        # Quantized resonant integrators can settle onto different small orbits.
        assert error_rms <= 64
        assert max(evidence["filter_peaks"]) < 131072
    finally:
        reference.close()


@pytest.mark.parametrize("cutoff", [0, 1, 0x6555, 0xFFFF])
@pytest.mark.parametrize("resonance", [0, 128, 255])
def test_filter_does_not_generate_sound_from_zero_state(chip, cutoff, resonance):
    chip.word(0, CUTOFF, cutoff)
    chip.write(0, RESON, resonance)
    chip.write(0, FLAGS0, 0xE0)
    assert not np.any(chip.render(4096))


@pytest.mark.regression
def test_ordinary_filter_response(chip, ndarrays_regression):
    # Baseline captured from the pre-fix core, not regenerated from the fix.
    responses = []
    chip.pcm([100, 0])
    for cutoff, resonance in STABLE_SETTINGS:
        chip.reset()
        chip.word(0, FREQ, 0x8000)
        chip.word(0, 0x2C, 1)
        chip.write(0, VOL, 16)
        chip.word(0, CUTOFF, cutoff)
        chip.write(0, RESON, resonance)
        chip.write(0, FLAGS0, 0x29)
        responses.append(chip.render(512)[:, 3])
    ndarrays_regression.check({"response": np.array(responses)},
                              default_tolerance={"atol": 0, "rtol": 0})
