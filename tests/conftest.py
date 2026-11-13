import hashlib
import importlib.util
from pathlib import Path

from cffi import FFI
import pytest

from sgu_testkit import Chip

ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption("--audio-artifacts", choices=["failed", "all", "none"],
                     default="failed", help="Save WAV/plots/metadata for audio tests")
    parser.addoption("--run-known-defects", action="store_true",
                     help="Treat documented core defects as ordinary failing tests")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-known-defects"):
        for item in items:
            marker = item.get_closest_marker("known_defect")
            if marker:
                item.add_marker(pytest.mark.xfail(reason=marker.kwargs["reason"],
                                                 strict=True, raises=AssertionError))


@pytest.fixture(scope="session")
def native(tmp_path_factory):
    builder = FFI()
    builder.cdef("""
        struct TestChip;
        struct TestChip *test_create(void);
        void test_destroy(struct TestChip *);
        void test_reset(struct TestChip *);
        void test_reset_parts(struct TestChip *, unsigned);
        void test_write(struct TestChip *, unsigned, unsigned);
        unsigned test_read(struct TestChip *, unsigned, unsigned);
        void test_pcm(struct TestChip *, unsigned, int);
        unsigned test_flags(struct TestChip *);
        void test_filter_peaks(struct TestChip *, int64_t *);
        void test_render(struct TestChip *, unsigned, unsigned, int, int32_t *);
    """)
    builder.set_source("_sgu_test_native", '#include "adapter.c"',
                       sources=[str(ROOT / "sgu.c")],
                       include_dirs=[str(ROOT), str(ROOT / "tests/native")],
                       libraries=["m"], extra_compile_args=["-std=gnu11", "-O2"])
    filename = builder.compile(tmpdir=str(tmp_path_factory.mktemp("native")))
    spec = importlib.util.spec_from_file_location("_sgu_test_native", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ffi, module.lib


@pytest.fixture
def evidence(request):
    request.node.audio_evidence = {}
    return request.node.audio_evidence


@pytest.fixture
def chip(native, evidence):
    instance = Chip(*native, evidence)
    yield instance
    instance.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    mode = item.config.getoption("--audio-artifacts")
    evidence = getattr(item, "audio_evidence", {})
    if (report.when != "call" or "samples" not in evidence or mode == "none"
            or (mode == "failed" and not (report.failed or hasattr(report, "wasxfail")))):
        return
    from audio_artifacts import save_artifacts
    directory = ROOT / "test-results" / hashlib.sha256(item.nodeid.encode()).hexdigest()[:16]
    save_artifacts(directory, item.nodeid, evidence)
    report.sections.append(("Audio artifacts", str(directory)))
    if item.config.pluginmanager.hasplugin("html"):
        import pytest_html
        import os
        report_path = Path(item.config.option.htmlpath or ROOT / "test-results/report.html")
        relative = Path(os.path.relpath(directory, report_path.resolve().parent)).as_posix()
        report.extras = getattr(report, "extras", []) + [
            pytest_html.extras.html(
                f'<a href="{relative}/metrics.json">Audio metadata</a><br>'
                f'<audio controls src="{relative}/output.wav"></audio><br>'
                f'<img src="{relative}/analysis.png" alt="Waveform, spectrum and spectrogram" style="max-width:100%">'),
        ]
