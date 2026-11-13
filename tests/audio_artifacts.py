"""Failure diagnostics; audio scaling is fixed to the hardware, never normalized."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.io import wavfile

from sgu_testkit import FULL_SCALE, SAMPLE_RATE, rms_dbfs, band_dbfs


def save_artifacts(directory, nodeid, evidence):
    directory.mkdir(parents=True, exist_ok=True)
    samples = evidence["samples"]
    stereo = samples[:, :2]
    np.save(directory / "raw.npy", samples)
    wavfile.write(directory / "output.wav", SAMPLE_RATE,
                  np.clip(stereo.astype(np.int64) >> 1, -32768, 32767).astype(np.int16))
    metadata = {key: value for key, value in evidence.items() if key != "samples"}
    metadata.update(test=nodeid, sample_rate=SAMPLE_RATE, full_scale=FULL_SCALE,
                    columns=["left", "right", "channel_raw", "channel_post"],
                    rms_dbfs=rms_dbfs(stereo), hiss_band_dbfs=band_dbfs(stereo[:, 0]) if len(stereo) >= 2 else None,
                    peak=int(np.abs(stereo.astype(np.int64)).max()))
    (directory / "metrics.json").write_text(json.dumps(metadata, indent=2) + "\n")
    x = stereo[:, 0].astype(float) / FULL_SCALE
    fig, axes = plt.subplots(4, 1, figsize=(10, 10), layout="constrained")
    times = np.arange(len(x)) / SAMPLE_RATE
    axes[0].plot(times, x, linewidth=0.5)
    axes[0].set(xlabel="Time (s)", ylabel="Full scale", title=nodeid)
    # Zoom around the greatest local curvature to make short impulses visible.
    center = int(np.argmax(np.abs(np.diff(x, n=2)))) + 1 if len(x) > 2 else 0
    start, end = max(0, center - 128), min(len(x), center + 128)
    axes[1].plot(times[start:end], x[start:end], linewidth=0.8)
    axes[1].set(xlabel="Time (s), largest curvature excerpt", ylabel="Full scale")
    f, psd = signal.welch(x, SAMPLE_RATE, nperseg=min(4096, len(x)), detrend=False)
    axes[2].plot(f, 10 * np.log10(np.maximum(psd, 1e-30)))
    axes[2].set(xlabel="Frequency (Hz)", ylabel="dBFS/Hz")
    if len(x) >= 256:
        with np.errstate(divide="ignore"):
            axes[3].specgram(x, NFFT=256, Fs=SAMPLE_RATE, noverlap=192,
                             vmin=-140, vmax=-20)
    axes[3].set(xlabel="Time (s)", ylabel="Frequency (Hz)")
    fig.savefig(directory / "analysis.png")
    plt.close(fig)
