"""Starting this plugin's own process inside the Hub's timeouts.

The failure these cover came from a real onboarding: the Hub reported
``PluginUIDaemon for 'synthetic_biology' failed ready handshake. Virtual
Environment connection failed! Stderr: Matplotlib is building the font cache``,
three times, each at 30.0 s after the daemon was launched.

Two causes, and both are the kind that only appear on a machine nobody
develops on:

* ``PluginUIDaemon`` allows **30 s** for the ready frame, and ``ui_daemon.py``
  imported every heavy dependency before that frame was sent. The cold
  matplotlib font-cache build alone is ~12 s of it; with no compiled bytecode
  and macOS verifying each shared library on first load, the total crossed 30 s
  and the plugin simply could not be opened.
* The Hub runs a per-plugin self-test after installing dependencies, which is
  exactly where that cost belongs — it allows 120 s and warns the user it may
  take a minute. This plugin shipped no self-test script, so the Hub logged
  "No self-test script found ... skipping" and called the install a success
  without the venv ever having been started.

So what is pinned here is: the self-test script exists at the path the Hub
looks for and speaks the protocol it speaks, the warm-up helpers cannot fail a
launch, and the expensive imports stay off the pre-handshake path.
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path

import msgpack
import pytest

from karcytics_plugins.synthetic_biology.analysis import startup

ROOT = Path(__file__).resolve().parents[2]

#: Where `karcytics.core.package_manager._run_selftest` looks, given a plugin
#: directory whose name is the plugin id. Hardcoded rather than derived,
#: because it is a contract with the Hub: move the file and the self-test
#: silently stops running again.
SELFTEST_SCRIPT = ROOT / "src/karcytics_plugins/synthetic_biology/analysis/daemon_worker.py"

UI_DAEMON = ROOT / "src/karcytics_plugins/synthetic_biology/ui_daemon.py"

_HEADER = ">I"


# ── The self-test script the Hub looks for ─────────────────────────────


@pytest.mark.unit
def test_the_selftest_script_is_where_the_hub_looks_for_it():
    assert SELFTEST_SCRIPT.exists(), (
        "the Hub resolves this exact path and skips the self-test when it is "
        "absent, which is how an install reported success without the venv "
        "ever being started"
    )


@pytest.mark.unit
def test_the_selftest_script_is_headless():
    """It runs during install, with no window and no QApplication.

    A Qt import here would make dependency installation depend on a working
    display, and on a headless lab machine that turns a warm-up into a
    failed install.
    """
    source = SELFTEST_SCRIPT.read_text(encoding="utf-8")
    # Past the module docstring, which describes this rule and would otherwise
    # match it.
    body = source[source.index("from __future__") :]

    assert "PySide6" not in body
    assert "QApplication" not in body


class _Worker:
    """The Hub's side of the worker protocol, as PluginDaemon speaks it."""

    def __init__(self, env: dict[str, str]):
        self.proc = subprocess.Popen(
            [sys.executable, str(SELFTEST_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def _read_exact(self, count: int) -> bytes:
        buf = bytearray()
        while len(buf) < count:
            chunk = self.proc.stdout.read(count - len(buf))  # type: ignore[union-attr]
            if not chunk:
                raise AssertionError(
                    "the worker closed stdout early; stderr was: "
                    + self.proc.stderr.read().decode(errors="replace")  # type: ignore[union-attr]
                )
            buf.extend(chunk)
        return bytes(buf)

    def read_frame(self) -> dict:
        length = struct.unpack(_HEADER, self._read_exact(4))[0]
        return msgpack.unpackb(self._read_exact(length), raw=False)

    def call(self, method: str, **kwargs) -> dict:
        payload = msgpack.packb({"method": method, "kwargs": kwargs}, use_bin_type=True)
        self.proc.stdin.write(struct.pack(_HEADER, len(payload)) + payload)  # type: ignore[union-attr]
        self.proc.stdin.flush()  # type: ignore[union-attr]
        return self.read_frame()

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=10)


@pytest.fixture(scope="module")
def worker_env(tmp_path_factory) -> dict[str, str]:
    """Environment for a worker: the real one, with user data redirected.

    `MPLCONFIGDIR` is deliberately inherited rather than redirected. Pointing
    it somewhere fresh makes every worker rebuild the font cache -- ~12 s each
    -- which is both slow here and the wrong thing to ask of a real install;
    see `startup`'s module docstring.
    """
    return dict(
        os.environ,
        KARCYTICS_PLUGIN_ID="synthetic_biology",
        KARCYTICS_SYNBIO_USER_DIR=str(tmp_path_factory.mktemp("userdir")),
        PYTHONUNBUFFERED="1",
    )


@pytest.fixture
def worker(worker_env):
    """A live self-test worker, speaking the real protocol over real pipes."""
    client = _Worker(worker_env)
    yield client
    client.close()


@pytest.mark.unit
def test_the_worker_announces_itself_ready(worker):
    """The first frame out must be exactly this, or the self-test fails."""
    assert worker.read_frame() == {"status": "ready"}


@pytest.mark.unit
def test_the_worker_answers_ping_with_pong(worker):
    """`_run_isolated_daemon_selftest` asserts on this and nothing else."""
    worker.read_frame()

    reply = worker.call("ping")

    assert reply["status"] == "pong"
    assert reply["python"].startswith("3."), "the log needs to say which interpreter ran"
    assert reply["warmed"], "a ping that warmed nothing means the venv is broken"


@pytest.mark.unit
def test_an_unknown_method_is_an_error_not_a_crash(worker):
    """A worker that dies on a bad frame turns a typo into a failed install."""
    worker.read_frame()

    reply = worker.call("no_such_method")

    assert "error" in reply
    assert worker.call("ping")["status"] == "pong", "it must still be serving"


@pytest.mark.unit
def test_the_worker_exits_cleanly_on_shutdown(worker):
    worker.read_frame()

    assert worker.call("shutdown") == {"status": "ok"}
    assert worker.proc.wait(timeout=15) == 0


@pytest.mark.unit
def test_the_worker_exits_when_its_input_closes(worker):
    """The Hub terminates by closing the pipe, not always by asking."""
    worker.read_frame()
    worker.proc.stdin.close()

    assert worker.proc.wait(timeout=15) == 0


# ── The warm-up helpers ────────────────────────────────────────────────


@pytest.mark.unit
def test_warm_imports_reports_what_it_loaded():
    assert startup.warm_imports(("json", "struct")) == ["json", "struct"]


@pytest.mark.unit
def test_warm_imports_skips_what_is_missing_without_raising():
    """A warm-up is never the only route to a dependency.

    Whatever is skipped gets imported again where it is actually needed, so an
    ImportError belongs to that feature rather than to startup.
    """
    assert startup.warm_imports(("json", "no_such_module_at_all")) == ["json"]


# ── The regression guard ───────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize("module", ["matplotlib.pyplot", "tellurium"])
def test_the_expensive_imports_stay_off_the_pre_handshake_path(module):
    """This is the bug, and it is a one-line edit away from coming back.

    Everything at module scope in `ui_daemon.py` runs before `run_ui_daemon()`
    is called, and the SDK sends its ready frame inside that call — so an
    import added here is spent against the 30 s handshake budget. A cold
    `matplotlib.pyplot` is ~12 s of it on its own.
    """
    source = UI_DAEMON.read_text(encoding="utf-8")
    body = source[: source.index("def _build_plugin_context")]

    assert f"import {module}" not in body, (
        f"{module} is imported before the ready handshake again; warm it through "
        "startup.WARM_MODULES instead, which runs on a thread"
    )


@pytest.mark.unit
def test_the_warm_list_covers_the_two_expensive_imports():
    assert "matplotlib.font_manager" in startup.WARM_MODULES, (
        "font_manager is where the entire cold font-cache build happens"
    )
    assert "tellurium" in startup.WARM_MODULES


@pytest.mark.unit
def test_numpy_is_imported_before_the_stdin_reader_thread_exists():
    """Order matters here, not just membership.

    Importing numpy while another thread is blocked on `sys.stdin.buffer.read`
    can deadlock on Windows, so it must be eager and it must be first.
    """
    assert startup.EAGER_MODULES[0] == "numpy"
    assert "numpy" not in startup.WARM_MODULES


@pytest.mark.unit
def test_startup_stays_single_threaded():
    """Overlapping these imports with the handshake was tried, and hung.

    The SDK's UI daemon runtime keeps a thread blocked on
    `sys.stdin.buffer.read`, and importing concurrently with it deadlocks: the
    daemon integration tests began timing out after 45 s waiting for a worker
    that never became serviceable. The cost is paid at install instead, where
    the Hub allows 120 s.
    """
    assert not hasattr(startup, "start_background_warmup"), (
        "a threaded warm-up deadlocks against the SDK's stdin reader"
    )
    for source in (SELFTEST_SCRIPT, UI_DAEMON):
        assert "threading" not in source.read_text(encoding="utf-8"), (
            f"{source.name} must not import during startup on another thread"
        )


@pytest.mark.unit
def test_both_daemons_warm_the_same_modules():
    """The launch-time cost is only cheap because the install-time run matched it.

    A dependency warmed in one and not the other reintroduces the cold cost on
    the budget that cannot afford it.
    """
    for source in (SELFTEST_SCRIPT, UI_DAEMON):
        assert "warm_imports(EAGER_MODULES + WARM_MODULES)" in source.read_text(encoding="utf-8"), (
            f"{source.name} does not warm the full list"
        )


# ── The self-test must actually verify, not just warm ─────────────────


@pytest.mark.unit
def test_a_complete_venv_answers_pong(worker):
    """The healthy path, stated next to the broken one for contrast."""
    worker.read_frame()

    assert worker.call("ping")["status"] == "pong"


@pytest.mark.unit
def test_an_incomplete_venv_fails_the_selftest(worker_env, tmp_path):
    """A missing core dependency must fail the install, not pass it.

    The Hub asserts `status == "pong"` and fails the install on anything else,
    so this is the last moment a broken venv can be reported to someone who
    can act on it. Answering pong here would install a module that opens and
    then dies at the first analysis.

    numpy is hidden with a stub that raises on import, which is as close to a
    genuinely broken install as a test can get without breaking the real venv.
    """
    sabotage = tmp_path / "sabotage"
    sabotage.mkdir()
    (sabotage / "numpy.py").write_text('raise ImportError("sabotaged for the test")\n')

    env = dict(worker_env, PYTHONPATH=str(sabotage))
    client = _Worker(env)
    try:
        client.read_frame()
        reply = client.call("ping")
    finally:
        client.close()

    assert reply.get("status") != "pong", "a broken venv must not pass the self-test"
    assert "numpy" in reply.get("missing", [])
    assert "numpy" in reply["error"]
    assert sys.executable.split("/")[-1] in reply["error"] or "python" in reply["error"], (
        "the message must name the interpreter that could not import it"
    )


@pytest.mark.unit
def test_the_required_set_is_what_the_plugin_cannot_run_without():
    """Kept small on purpose: everything else backs one feature.

    A long required list turns any optional dependency's absence into a failed
    install, which is a worse outcome than that feature raising where it is
    used.
    """
    assert set(startup.REQUIRED_MODULES) == {"numpy", "scipy", "msgpack", "Bio.Seq"}
    for optional in ("matplotlib.font_manager", "tellurium", "pyqtgraph"):
        assert optional not in startup.REQUIRED_MODULES


@pytest.mark.unit
def test_missing_required_names_only_what_is_absent():
    assert startup.missing_required(("json", "struct")) == []
    assert startup.missing_required(("json", "no_such_module_at_all")) == ["no_such_module_at_all"]
