"""Getting this plugin's heavy dependencies imported without blowing a timeout.

The failure this exists to prevent
----------------------------------
``PluginUIDaemon`` starts the plugin's own interpreter and waits **30 seconds**
for a ready frame (``karcytics_sdk.plugin.daemon``). On a first launch the
import of ``matplotlib.font_manager`` builds matplotlib's font cache from
scratch, which is not a quick job:

    matplotlib.font_manager   12.4 s     <- cold cache
    tellurium                  1.8 s
    pyqtgraph                  0.2 s
    numpy + scipy              0.1 s
    networkx, Bio, requests    0.3 s

That is ~15 s measured on a fast machine with bytecode already compiled. A
fresh install has neither: every one of the eighteen dependencies is compiled
to bytecode on its first import, and on macOS a translocated app bundle has
Gatekeeper verifying each shared library as it is loaded. The total crosses 30
seconds, the handshake fails, and the Hub reports "Virtual Environment
connection failed!" with matplotlib's own "building the font cache" line as the
only clue.

It is also self-perpetuating in the worst case: the daemon is killed at 30 s,
so if the cache had not finished being written, the next launch rebuilds it and
is killed again.

What fixes it
-------------
**The cache is built at install time, not at launch.**
``analysis/daemon_worker.py`` runs :func:`warm_imports` before answering the
Hub's self-test, where the budget is 120 seconds and the user has been told to
expect a minute. By the time the UI daemon first starts, the font cache is on
disk and every one of these imports is a fast path.

That is the whole fix, and it is deliberately the *only* fix. Two tidier-looking
alternatives were tried and both were worse:

*Warming on a background thread*, to overlap the cost with the handshake,
dropped the blocking cost from 15 s to 0.7 s and then hung the worker. The SDK's
UI daemon runtime keeps a thread blocked on ``sys.stdin.buffer.read``, and
importing concurrently with it deadlocks — the warning in
``karcytics_sdk.plugin.ui_daemon_runtime`` is about numpy on Windows, but the
hazard is not specific to either: it showed up here as the daemon integration
tests intermittently timing out after 45 s waiting for a worker that never
became serviceable. Startup in this process is single-threaded on purpose.

*Pointing ``MPLCONFIGDIR`` at a plugin-owned directory* abandons whatever
``~/.matplotlib`` already holds, so it made cold starts more likely rather than
less; it also made every short-lived worker rebuild the cache, taking those same
tests from 29 s to 137 s. matplotlib names its cache file after its own version
(``fontlist-v3.11.0.json``), so sharing that directory with the Hub's bundled
copy was never a conflict needing a fix.

So both daemons import the same list, synchronously, on the main thread. The
only difference between them is the budget they spend it against, and the
install-time one is what makes the launch-time one cheap.

No Qt imports.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: The subset the plugin genuinely cannot run without. If one of these fails to
#: import, the venv is broken and the install should say so rather than hand the
#: user a module that opens and then fails at the first analysis. Everything
#: else is warmed leniently: matplotlib, tellurium, pyqtgraph, networkx and
#: requests each back a feature, and a feature's own ImportError at the point of
#: use is a better error than a failed install.
REQUIRED_MODULES: tuple[str, ...] = (
    "numpy",
    "scipy",
    "msgpack",
    "Bio.Seq",
)

#: Imports done on the main thread. numpy is first and deliberately so: the
#: SDK's UI daemon runtime starts a thread blocked on ``sys.stdin.buffer.read``,
#: and importing numpy while that read is in flight can deadlock on Windows
#: (documented in ``karcytics_sdk.plugin.ui_daemon_runtime``). Importing it
#: before that thread exists makes every later import a sys.modules hit. The
#: rest here are cheap and pull Qt, which belongs on the main thread.
EAGER_MODULES: tuple[str, ...] = (
    "numpy",
    "scipy",
    "msgpack",
    "pyqtgraph",
    "networkx",
    "Bio.Seq",
    "Bio.SeqUtils.MeltingTemp",
    "requests",
)

#: Imports moved off the main thread. Both are expensive and neither touches
#: Qt: ``matplotlib.font_manager`` is where the entire font-cache build happens
#: (``matplotlib.pyplot`` costs 0.16 s once it is warm, and is left to be
#: imported on the main thread where backend selection belongs), and tellurium
#: loads libroadrunner's C extensions.
WARM_MODULES: tuple[str, ...] = (
    "matplotlib.font_manager",
    "tellurium",
)


def warm_imports(modules: tuple[str, ...] = WARM_MODULES) -> list[str]:
    """Import `modules`, ignoring any that are absent. Returns what loaded.

    Every failure is swallowed deliberately. This is a cache-warming pass, and
    nothing here is the plugin's only route to a dependency — whatever is
    skipped is imported again, for real, at the point it is first needed, where
    an ImportError belongs to the feature that wanted it rather than to
    startup.
    """
    loaded: list[str] = []
    for name in modules:
        try:
            __import__(name)
        except Exception:  # noqa: BLE001 - a warm-up must never fail a launch
            logger.debug("Warm-up import of %s did not succeed", name, exc_info=True)
        else:
            loaded.append(name)
    return loaded


def missing_required(modules: tuple[str, ...] = REQUIRED_MODULES) -> list[str]:
    """Which of `modules` cannot be imported, in order.

    Separate from :func:`warm_imports` because the two have opposite jobs: that
    one must never fail a launch, this one exists to fail an *install*. The
    Hub's self-test is the only place a missing dependency can still be
    reported to someone who can act on it -- after that the plugin is installed
    and the same fault arrives as a traceback mid-analysis.
    """
    absent: list[str] = []
    for name in modules:
        try:
            __import__(name)
        except Exception:  # noqa: BLE001 - a broken module counts as missing
            absent.append(name)
    return absent
