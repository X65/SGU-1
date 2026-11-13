import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from sgu_testkit import Chip, FREQ, FLAGS0, FLAGS1, VOL, PAN, frequency_word


def test_reset_is_exact_silence(chip):
    assert not np.any(chip.render(48000))
    chip.tone()
    assert np.any(chip.render(1024))
    chip.reset()
    assert not np.any(chip.render(48000))


def test_reset_replays_identically(chip):
    chip.tone(wave=4)
    expected = chip.render(8192)
    chip.reset()
    chip.tone(wave=4)
    np.testing.assert_array_equal(chip.render(8192), expected)


@pytest.mark.parametrize("split", range(10))
def test_split_render_matches_single_call(chip, native, evidence, split):
    def configure(target):
        for channel in range(9):
            target.tone(hz=110 + channel * 37, channel=channel, volume=8,
                      wave=channel % 5)
    configure(chip)
    expected = chip.render(8192)
    other = Chip(*native, evidence)
    try:
        configure(other)
        np.testing.assert_array_equal(other.render(8192, split=split), expected)
    finally:
        other.close()


def test_buffer_sizes_do_not_change_sample_timed_events(chip):
    def play(block_size):
        chip.reset()
        chip.tone()
        chunks = []
        for target, hz in [(997, 880), (2051, 220), (4096, 440)]:
            while chip.position < target:
                chunks.append(chip.render(min(block_size, target - chip.position)))
            chip.word(0, FREQ, frequency_word(hz))
        return np.concatenate(chunks)
    np.testing.assert_array_equal(play(1), play(257))


@pytest.mark.parametrize("pan,silent,active", [(127, 0, 1), (128, 1, 0)])
def test_pan_endpoints(chip, pan, silent, active):
    chip.tone()
    chip.write(0, PAN, pan)
    samples = chip.render(4096)
    assert not np.any(samples[:, silent])
    assert np.max(np.abs(samples[:, active])) > 1000


def test_clip_flag_is_sticky_and_clears_on_read(chip):
    for channel in range(9):
        for operator in range(4):
            chip.tone(channel=channel, operator=operator, volume=127)
    output = chip.render(4096)[:, :2]
    assert np.any((output < -65536) | (output > 65535))
    assert chip.lib.test_flags(chip.handle) & 1
    assert chip.lib.test_flags(chip.handle) == 0


@pytest.mark.parametrize("rate", [0x2000, 0x4000, 0x8000])
def test_pcm_exact_sequence_and_loop(chip, rate):
    pcm = np.array([-100, -40, 10, 70, 110, 35, -15, -80], dtype=np.int8)
    chip.pcm(pcm)
    chip.word(0, FREQ, rate)
    chip.word(0, 0x2C, len(pcm))
    chip.word(0, 0x2E, 0)
    chip.write(0, VOL, 64)
    chip.write(0, FLAGS0, 9)
    chip.write(0, FLAGS1, 4)
    audio = chip.render(100)
    positions = (np.arange(100) * rate // 0x8000) % len(pcm)
    np.testing.assert_array_equal(audio[:, 2], pcm[positions].astype(np.int32) * 64)
    chip.write(0, FLAGS0, 8)
    before = chip.read(0, 0x2A)
    assert not np.any(chip.render(123)[:, 2])
    assert chip.read(0, 0x2A) == before
    chip.write(0, FLAGS0, 9)
    assert chip.render(1)[0, 2] == int(pcm[before]) * 64


@given(st.lists(st.tuples(st.integers(0, 8), st.integers(0, 63),
                         st.integers(0, 255)), min_size=1, max_size=30))
@settings(max_examples=30, deadline=None)
def test_register_writes_are_isolated(native, writes):
    # A fresh native instance per generated example, without rendering one-shots.
    instance = Chip(*native, {})
    expected = np.zeros((9, 64), dtype=np.uint8)
    try:
        for channel, reg, value in writes:
            # DIAG changes read semantics, so keep it disabled for this property.
            if reg == FLAGS1:
                value &= 127
            instance.write(channel, reg, value)
            expected[channel, reg] = value
        actual = [[instance.read(ch, reg) for reg in range(64)] for ch in range(9)]
        np.testing.assert_array_equal(actual, expected)
    finally:
        instance.close()


@pytest.mark.known_defect(reason="SGU_Reset leaves BLEP history, causing a transient when replaying a sine")
def test_reset_clears_waveform_history(chip):
    chip.tone(hz=110, volume=8)
    expected = chip.render(8192)
    chip.reset()
    chip.tone(hz=110, volume=8)
    np.testing.assert_array_equal(chip.render(8192), expected)


def test_trigger_and_phase_reset_requests_self_clear(chip):
    chip.tone()
    chip.write(0, FLAGS0, 3)
    chip.write(0, FLAGS1, 3)
    chip.render(1)
    assert chip.read(0, FLAGS0) == 1
    assert chip.read(0, FLAGS1) == 0


def test_volume_sweep_stops_at_bound(chip):
    chip.tone(volume=16)
    chip.word(0, 0x34, 4)
    chip.write(0, 0x36, 0x21)  # Up, step one, one-shot.
    chip.write(0, 0x37, 32)
    chip.write(0, FLAGS1, 0x20)
    volumes = []
    for _ in range(128):
        chip.render(1)
        volumes.append(chip.read(0, VOL))
    assert all(a <= b for a, b in zip(volumes, volumes[1:]))
    assert volumes[-1] == 32
    assert volumes.count(32) > 32
