"""Register fixtures and independent acoustic measurements for SGU-1."""
import numpy as np
from scipy import signal

SAMPLE_RATE = 48000
FULL_SCALE = 65536  # Hardware clips the core mix after its one-bit right shift.
FREQ, VOL, PAN, FLAGS0, FLAGS1 = 0x20, 0x22, 0x23, 0x24, 0x25
CUTOFF, RESON = 0x26, 0x29


def frequency_word(hz):
    word = round(hz * 2**24 / 1_000_000)
    if not 0 <= word <= 65535:
        raise ValueError("Frequency outside the channel register range")
    return word


def represented_hz(word):
    # SID frequency semantics; independent of the core's integer phase helper.
    return word * 1_000_000 / 2**24


class Chip:
    def __init__(self, ffi, lib, evidence):
        self.ffi, self.lib, self.evidence = ffi, lib, evidence
        self.handle = lib.test_create()
        if self.handle == ffi.NULL:
            raise MemoryError("Cannot allocate SGU test chip")
        self.events = []
        self.position = 0

    def close(self):
        self.lib.test_destroy(self.handle)

    def reset(self):
        self.lib.test_reset(self.handle)
        self.position = 0
        self.events = []

    def write(self, channel, reg, value):
        if not (0 <= channel < 9 and 0 <= reg < 64 and 0 <= value < 256):
            raise ValueError("Invalid register write")
        self.lib.test_write(self.handle, channel * 64 + reg, value)
        self.events.append([self.position, channel, reg, value])

    def word(self, channel, reg, value):
        if not 0 <= value <= 65535:
            raise ValueError("Invalid 16-bit register value")
        self.write(channel, reg, value & 255)
        self.write(channel, reg + 1, value >> 8)

    def read(self, channel, reg):
        if not (0 <= channel < 9 and 0 <= reg < 64):
            raise ValueError("Invalid register read")
        return self.lib.test_read(self.handle, channel, reg)

    def pcm(self, samples):
        samples = np.asarray(samples)
        if len(samples) > 65536 or np.any(samples < -128) or np.any(samples > 127):
            raise ValueError("Invalid signed 8-bit PCM")
        for address, value in enumerate(samples):
            self.lib.test_pcm(self.handle, address, int(value))

    def render(self, count, channel=0, split=-1):
        if count <= 0 or not 0 <= channel < 9 or not -1 <= split <= 9:
            raise ValueError("Invalid render arguments")
        samples = np.empty((count, 4), dtype=np.int32)
        self.lib.test_render(self.handle, count, channel, split,
                             self.ffi.from_buffer("int32_t[]", samples))
        peaks = self.ffi.new("int64_t[3]")
        self.lib.test_filter_peaks(self.handle, peaks)
        self.evidence.update(filter_peaks=list(peaks))
        self.evidence.update(samples=samples, start_sample=self.position,
                             events=list(self.events), channel=channel)
        self.position += count
        return samples

    def tone(self, hz=440, channel=0, operator=0, multiplier=1, wave=0,
             volume=64, fixed=False, detune=0, attenuation=0):
        base = operator * 8
        for offset, value in enumerate([
            multiplier, attenuation & 63, 0xF0, 0x0F, detune << 5,
            0x10 if fixed else 0, (attenuation >> 6) & 1, 0xF0 | wave,
        ]):
            self.write(channel, base + offset, value)
        self.word(channel, FREQ, frequency_word(hz))
        self.write(channel, VOL, volume)
        self.write(channel, PAN, 0)
        self.write(channel, FLAGS0, 1)


def estimate_frequency(samples):
    """Average interpolated rising crossings of a controlled, clean sine."""
    x = np.asarray(samples, dtype=float)
    x = x - x.mean()
    crossings = np.flatnonzero((x[:-1] <= 0) & (x[1:] > 0))
    if len(crossings) < 4:
        raise ValueError("Need at least four rising crossings")
    times = crossings - x[crossings] / (x[crossings + 1] - x[crossings])
    period = np.polyfit(np.arange(len(times)), times, 1)[0]
    return SAMPLE_RATE / period


def estimate_spectral_peak(samples):
    """Strongest tone, resolved to Fs/(4*N); suitable for high-frequency pitch."""
    frequencies, power = signal.periodogram(
        np.asarray(samples, dtype=float), fs=SAMPLE_RATE, window="hann",
        nfft=4 * len(samples),
    )
    return float(frequencies[np.argmax(power)])


def rms_dbfs(samples):
    rms = np.sqrt(np.mean(np.asarray(samples, dtype=float)**2)) / FULL_SCALE
    return float(20 * np.log10(max(rms, 1e-15)))


def band_dbfs(samples, low=8000, high=20000):
    frequencies, psd = signal.welch(
        np.asarray(samples, dtype=float) / FULL_SCALE,
        fs=SAMPLE_RATE, nperseg=min(4096, len(samples)), detrend=False,
    )
    selected = (frequencies >= low) & (frequencies <= high)
    power = np.sum(psd[selected]) * (frequencies[1] - frequencies[0])
    return float(10 * np.log10(max(power, 1e-30)))


def sine_residual(samples, hz):
    x = np.asarray(samples, dtype=float)
    phase = 2 * np.pi * hz * np.arange(len(x)) / SAMPLE_RATE
    basis = np.column_stack((np.sin(phase), np.cos(phase), np.ones(len(x))))
    return x - basis @ np.linalg.lstsq(basis, x, rcond=None)[0]


def tick_indices(samples, threshold=64):
    """Local prediction error; only valid for our smooth-sine fixtures."""
    x = np.asarray(samples, dtype=float)
    return np.flatnonzero(np.abs(x[1:-1] - (x[:-2] + x[2:]) / 2) > threshold) + 1
