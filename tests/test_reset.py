"""A voice reset must discard previous oscillator and modulation history."""
import numpy as np
import pytest


@pytest.mark.parametrize("channel", range(9))
@pytest.mark.parametrize("operator", range(4))
@pytest.mark.parametrize("wave", [0, 1, 2, 3, 4, 5, 7],
                         ids=["sine", "triangle", "saw", "pulse", "noise", "periodic", "sample"])
def test_reset_replays_every_voice(chip, channel, operator, wave):
    if wave == 7:
        chip.pcm(np.tile(np.arange(-128, 128, dtype=np.int16), 4))

    def configure():
        chip.tone(hz=110, volume=8, channel=channel, operator=operator, wave=wave)
        chip.write(channel, 0x28, 64)

    configure()
    expected = chip.render(8192, channel)
    assert np.any(expected[:, 2])
    chip.reset()
    configure()
    np.testing.assert_array_equal(chip.render(8192, channel), expected)


@pytest.mark.parametrize("parts", [1, 7], ids=["voices-only", "full"])
@pytest.mark.parametrize("routing", ["feedback", "fm", "ring"])
def test_reset_discards_modulation_history(chip, parts, routing):
    def configure():
        for operator in range(4):
            chip.tone(hz=110, operator=operator, volume=8, multiplier=operator + 1)
            # MOD=7: op0 feedback or input from preceding operator.
            chip.write(0, operator * 8 + 6, 0x10 if routing == "ring" else
                       (14 if routing == "fm" or operator == 0 else 0))

    configure()
    expected = chip.render(8192)
    chip.lib.test_reset_parts(chip.handle, parts)
    configure()
    actual = chip.render(8192)
    # VOICES leaves the output DC filter/timebase intact. With LFOs off and
    # immediate attack, the raw voice must nevertheless replay exactly.
    np.testing.assert_array_equal(actual if parts == 7 else actual[:, 2],
                                  expected if parts == 7 else expected[:, 2])
