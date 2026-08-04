# Bumping `sortition-algorithms` 0.11.5 → 0.12.10

Status: **researched and planned, not started.** Deliberately deferred out of the Eel→Qt
port (see `llm-working/eel-to-qt.md`, decision D5) so that port stayed a like-for-like
comparison. This is its own PR, to be done afterwards.

Everything below was checked against the sibling checkout at
`ignore/repos/sortition-algorithms` (tags `0.11.5` and `0.12.10`, ~100 commits apart) and
against this app's own source and tests. Where the earlier sketch guessed, the guesses are
corrected in place and called out — two of the three things it named as risks turn out not
to be risks at all, and the two biggest real issues (a dependency that would add ~180 MB to
the bundle, and three tests that will fail) were not on the list.

Chewie has answered the open questions and nothing is left hanging; the decisions are listed
in §8 and folded into the sections they affect. Upstream issues to raise against
`sortition-algorithms` are collected in `llm-working/upstream.md`.

---

## 1. Why do it

1. **Progress reporting.** 0.12 adds a `ProgressReporter` protocol (`start_phase` /
   `update` / `end_phase`) and threads it through every algorithm. That turns the app's
   indeterminate busy indicator into a real `QProgressBar` — determinate for the phases
   that report a `total`, busy for the convergence loops where `total is None`. On a
   10-minute run over a real pool that is the difference between "working" and "possibly
   hung".
2. **The bundle gets smaller and the macOS story gets better.** `pandas` and
   `scikit-learn` moved from hard dependencies to an optional `diversimax` extra, and the
   default solver moved from python-mip/CBC to `highspy`. Between them that removes
   ~68 MB of installed weight from the default set (see §4) and removes the _reason_ the
   macOS build is pinned to x86_64.
3. **Not being 12 releases behind.** Latest tag is 0.12.10; we are pinned at 0.11.5. There
   are real bug fixes in the gap that this app is exposed to — non-string spreadsheet
   header cells, whitespace in header names, blank-ID rows, a helpful error for a `.xlsx`
   uploaded to Drive instead of a native Sheet.
4. **New capability we don't expose** — `load_already_selected` (replacements). Still a
   feature decision, not part of the bump. See §7.

---

## 2. What actually changed — the researched version

### 2.1 Corrections to the earlier sketch

| Earlier claim                                                                                                                  | Reality                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "0.12 has a `GSheetTabNamer`… the current app assigns `data_source.selected_tab_name` directly… **the main risk in the bump**" | **Wrong on both halves.** `GSheetTabNamer` already exists in 0.11.5, unchanged in 0.12.10 (byte-identical class). And this app never assigns `selected_tab_name` — `grep -rn "selected_tab_name" strat_app` returns nothing. The old Eel `script.py` did; the session-layer extraction (`f5de19a`) dropped it. `GSheetDataSource.selected_tab_name` is a vestigial attribute on both versions, set in `__init__` and read by nobody. `tests/fakes.py:98-99` mirrors it for the same non-reason. **Not a risk. Not work.** |
| "`RunReport` shape — new `message_code` / `message_params` fields on report lines"                                             | Already present in 0.11.5. `git diff 0.11.5 0.12.10 -- src/sortition_algorithms/utils.py` touches only `normalise_iter` (new) and `normalise_dict` (now strips keys as well as values). `RunReport`, `as_html()`, `as_text()`, `add_line`, `add_report`, `ReportLevel` are all unchanged. **Not a risk.**                                                                                                                                                                                                                 |
| "Deprecations — `add_lines()` already warns; check whether anything the app calls is on the way out"                           | `add_lines()` is still there, still deprecated, and this app never calls it. Nothing else the app touches is deprecated. **Not a risk.**                                                                                                                                                                                                                                                                                                                                                                                  |
| "Transitive dependency churn… re-measure the packaged size"                                                                    | Right instinct, wrong shape — the churn is much bigger than "versions move", and one of the moves is actively dangerous. See §4.                                                                                                                                                                                                                                                                                                                                                                                          |

### 2.2 The real API surface this app touches

Every library symbol the app uses, and its fate:

| Used by the app                                                        | 0.12.10                                                                                 |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `Settings.load_from_file()`                                            | unchanged signature; validation errors now `ConfigurationError` not `ValueError` (§2.4) |
| `adapters.CSVStringDataSource(features, people)`                       | unchanged                                                                               |
| `adapters.GSheetDataSource(...)`                                       | unchanged, **plus** new optional `request_timeout=60` kwarg                             |
| `adapters.SelectionData(source, gen_rem_tab=)`                         | unchanged                                                                               |
| `.load_features()` / `.load_people()` / `.output_selected_remaining()` | unchanged signatures and return types                                                   |
| `core.run_stratification(...)`                                         | **new `progress_reporter` kwarg**; retry loop removed (§2.3)                            |
| `core.selected_remaining_tables(...)`                                  | unchanged                                                                               |
| `features.minimum_selection` / `maximum_selection`                     | unchanged                                                                               |
| `People.count`                                                         | unchanged (`__len__` added alongside)                                                   |
| `RunReport`, `ReportLevel`, `as_html(include_logged=)`                 | unchanged                                                                               |
| logger name `sortition_algorithms_user`                                | unchanged                                                                               |

So no import breaks and no signature breaks. The breakage is all behavioural.

### 2.3 The retry loop moved — this is what breaks the tests

`run_stratification` used to wrap `find_random_sample` in `for tries in range(settings.max_attempts)` and log `"Trial number: N"` at the top of every attempt. In 0.12 (commit
`6722b9a`) that loop moved _into the legacy algorithm's wrapper_, which is the only
algorithm that ever benefited from it. Consequences:

- **`"Trial number: 1"` is no longer emitted unless `selection_algorithm = "legacy"`.**
  Our default is `maximin`. Three tests assert on that exact string and will fail (they
  will hang to their `waitUntil` timeout, then fail):
  - `tests/integration/test_threaded_selection.py:95`
  - `tests/integration/test_threaded_selection.py:112-113`
  - `tests/e2e/test_csv_flow.py:93`
- `"Failed N times. Gave up."` (`selection_failed`) likewise only appears for legacy now.
- The live-log-during-a-run behaviour those tests are actually about is **still fine**:
  `find_distribution_maximin` calls `report.add_message_and_log("using_maximin_algorithm",
logging.INFO)` as its first statement, before any solver work, so a line still reaches
  `sortition_algorithms_user` early in the run. The tests should key off
  `"Using maximin algorithm"` instead. That is a genuinely better test — it asserts the
  thing the app cares about (a line arrives while the work is in flight) rather than an
  incidental artefact of the retry loop.
  - Note `test_threaded_selection.py:96` already asserts `any("algorithm" in line ...)`,
    which passes unchanged. The two assertions in one test are now redundant with each
    other; collapse them.

**Decided: the `user_logger` bridge stays**, even once there is a progress bar. The two
say different things — the log says _what_ is happening ("Using maximin algorithm", "All
agents are contained in some feasible committee"), the bar says _how far_. Neither replaces
the other, so `user_log_handler` in `__main__.py` and `UserLogHandler` in `workers.py` are
untouched by this PR.

### 2.4 `ValueError` → `ConfigurationError`, and one escape route

0.12 introduces `ConfigurationError(SortitionBaseError)`. Note **`SortitionBaseError`
subclasses `Exception`, not `ValueError`.** Several things that raised `ValueError` in
0.11.5 now raise `ConfigurationError`, and `run_stratification`'s except clause is
`except (errors.SelectionError, ValueError, RuntimeError, errors.InfeasibleQuotasCantRelaxError)`
— which no longer catches them. So they propagate out of `run_stratification` instead of
being turned into `(False, [], report)`.

The one the app can actually hit: **test panel + `number_selections > 1`**. The gsheet tab
warns about this (`_multiple_selections_warning`) but does not disable the button, so a
user can do it. Today they get a tidy report and "No panels written to spreadsheet,
process ended."; after the bump they get `_selection_failed`'s generic "Unexpected error
during selection: …". Not a crash, but a downgrade.

**Decided: do both.** In the app, disable `run_test_button` when
`number_selections > 1`, which is what the warning already promises — _"You cannot use the
'Produce a Test Panel' button"_ — and currently doesn't enforce. That belongs in
`GSheetSession.set_number_selections`, pushed to the view through the existing
`set_run_enabled`-style path rather than by reaching into the widget, plus a unit test that
the test button goes disabled at 2 and re-enabled at 1. Separately, the upstream
inconsistency (`ConfigurationError` escaping where `ValueError` used to be caught) is
issue 1 in `llm-working/upstream.md`.

Other `ConfigurationError` sites (invalid `selection_algorithm`, invalid `solver_backend`,
`check_same_address` with no columns) are raised from `Settings` construction, which
`SettingsHolder.init_settings` already catches as bare `Exception`. No change needed.

### 2.5 New setting: `solver_backend`

`SOLVER_BACKENDS = ("highspy", "mip", "mip-cbc", "mip-highs", "mip-gurobi")`,
`DEFAULT_BACKEND = "highspy"`. The default `Settings` field means an existing
`~/sf_stratification_settings.toml` without the key keeps working. But the newly written
default settings file gains a `solver_backend = "highspy"` line, and — critically for §4 —
**the default solve now goes through `highspy`, not python-mip/CBC.**

Also worth knowing: the default-settings comment in the library is out of step with the
code — it says `# solver_backend can be "highspy" "mip" (default), ...` while
`DEFAULT_BACKEND = "highspy"`. Cosmetic upstream nit; issue 3 in
`llm-working/upstream.md`.

### 2.6 Behaviour and message changes users may notice

- `InfeasibleQuotasError`'s first line changed from _"The quotas are infeasible:"_ to
  _"It is not possible to hit all the targets with the current set of people. I suggest the
  following steps:"_. Friendlier; no test depends on it.
- Duplicate-ID reporting rewritten: now names the row numbers
  (`id_2 (rows 3 and 5)`) instead of dumping every column of every duplicate row. Strictly
  better for our users, who are staring at a spreadsheet.
- `finished_writing_selected_only` now explains _why_ only selected was written.
- `normalise_dict` now strips whitespace from **keys** as well as values, and headers go
  through the new `normalise_iter` — so a Google Sheet with `" nationbuilder_id"` in the
  header row now works where it previously produced a confusing parse error. Real fix for a
  real support burden.
- Blank-ID rows are skipped before the duplicate check (`0f64642`) — previously a run of
  empty rows under the data could trip the duplicate detector.
- New `NotNativeGoogleSheetError`, raised _before_ opening a Drive file that isn't a native
  Sheet (the classic "user uploaded an .xlsx"). It's a `SelectionError`, so our
  `_read_features` catch-all already reports it. **Decided: show the library's message
  and nothing more** — no special-casing in `gsheet_session`. If the wording turns out to be
  thin when we hit it in step 5's manual check, the fix belongs upstream in
  `error_messages.py` where every caller benefits, not in this app.
- `GSheetDataSource` now takes `request_timeout` (default 60s) and calls
  `client.set_timeout()`. **Decided: leave it at the default**, and don't expose it.
  It is a behaviour change for anyone on a slow connection with a very large respondents tab
  — previously the request would block indefinitely, now it fails after a minute — but a
  hung app is worse than a clear failure, and we can revisit if anyone hits it.
- One extra Drive API call per spreadsheet open (the mimetype check). Negligible.

### 2.7 Messages the app's tests assert on — all still present

Checked individually against `report_messages.py` / `settings.py` at 0.12.10:
`features_found` ("Number of features found: %(count)s") ✓, `wrote_default_settings`
("Wrote default settings to…") ✓, `tab_not_found` ("no tab called '…'") ✓. The
`RecordingLogView.text()` / `as_text()` path is unchanged. So beyond the three
`"Trial number: 1"` assertions in §2.3, no other test string is at risk — but see step 1 in
§5, we find out by running rather than by reading.

---

## 3. Progress reporting: what the library actually gives us

Phases emitted (from `docs/progress.md`, which the library treats the `name` values as
public API):

| `name`                   | `total`                                         | when                                                |
| ------------------------ | ----------------------------------------------- | --------------------------------------------------- |
| `legacy_attempt`         | `max_attempts`                                  | legacy only                                         |
| `multiplicative_weights` | `multiplicative_weights_rounds` (typically 200) | initial committee search — **maximin/leximin/nash** |
| `maximin_optimization`   | `None`                                          | maximin convergence loop                            |
| `nash_optimization`      | `None`                                          | nash convergence loop                               |
| `leximin_outer`          | `people.count`                                  | leximin outer loop                                  |
| `diversimax`             | `None`                                          | one event, no updates                               |

For our default (`maximin`) a run is therefore: `multiplicative_weights` (determinate,
~200 rounds — this is the long bit) → `maximin_optimization` (indeterminate). That maps
cleanly onto `QProgressBar`: `setRange(0, total)` when `total` is not `None`,
`setRange(0, 0)` when it is. `message` is always supplied by the library and is
human-readable ("Round 47/200: 31 committees found"), so it can go straight into a label
next to the bar.

Contract details that matter for the implementation:

- **Phases are flat.** Each `start_phase` implicitly ends the previous one. No nesting to
  model.
- **The library never throttles.** `update()` is called every iteration of the inner loop —
  "hundreds of times per second on a fast solver". Throttling is explicitly the caller's
  job. Emitting a Qt signal per call would flood the GUI thread's event queue.
- **Exceptions from the reporter are swallowed and logged** by `ErrorSwallowingReporter`
  (which `coerce_reporter` wraps ours in). So a bug in our reporter cannot kill a run — and
  equally, **Cancel cannot be implemented by raising from the reporter**. See §7.
- **Single-threaded from the library's side**, called from whichever thread we run the
  work on (our `QThread`). Signal emission across threads with a queued connection is the
  right bridge and needs no locking of our own.

Two reference implementations to crib from: `progress_rich.py` in the library (rich, no
throttling, single task) and OpenDLP's `DatabaseProgressReporter`
(`backend/src/opendlp/adapters/sortition_progress.py`) which is the throttled shape we
want — `time.monotonic()`, `min_interval_seconds`, `force=True` on phase transitions.

---

## 4. Packaging — the thing that isn't in the old plan and matters most

### 4.1 The resolution

Resolved with the app's real constraint set (`requires-python >=3.11,<3.13`,
`exclude-newer = "1 week"`) in a scratch project:

|                | 0.11.5 (current lock)               | 0.12.10                                           |
| -------------- | ----------------------------------- | ------------------------------------------------- |
| `pandas`       | 3.0.3 (27 MB installed)             | **gone**                                          |
| `scikit-learn` | 1.8.0 (18 MB) + `joblib`            | **gone** (`joblib` remains, via cvxpy)            |
| `mip`          | 1.15.0 (23 MB, CBC bundled inside)  | 1.17.6 (88 KB)                                    |
| `cbcbox`       | —                                   | **2.929 — new, and it is 181 MB on linux-x86_64** |
| `highspy`      | 1.14.0 (3.8 MB, pulled in by cvxpy) | 1.15.1, now a direct dependency                   |
| `cvxpy`        | 1.8.2                               | 1.9.2                                             |
| `numpy`        | 2.4.4                               | 2.4.6 / 2.5.1                                     |
| `scipy`        | 1.17.1                              | 1.17.1 / 1.18.0                                   |

`mip` 1.17 stopped vendoring CBC and moved it into a separate `cbcbox` wheel. The wheels
are **181 MB (linux x86_64), 145 MB (linux aarch64), 135 MB (win_amd64), 88 MB
(macos x86_64), 60 MB (macos arm64)**. `mip` is still a _hard_ dependency of
`sortition-algorithms`, so `uv sync` will install it and PyInstaller will happily collect
it. The current Linux binary is **157 MB**; naively bumping would push it far past 250 MB.

### 4.2 What to do about it

We don't need mip. The default backend is `highspy`, and `solver.py` computes
`MIP_AVAILABLE = importlib.util.find_spec("mip") is not None` at import time, then imports
`mip` lazily inside `MipSolver.__init__`. So:

- add `"mip"` and `"cbcbox"` to the spec's `EXCLUDES`;
- **delete `pyinstallerhooks/hook-mip.py`** and drop `hookspath=["pyinstallerhooks"]` (that
  hook exists solely to work around python-mip's `.so` collection, coin-or/python-mip#198,
  and there is nothing else in the directory);
- verify in the packaged build that `find_spec("mip")` returns `None` under PyInstaller's
  `FrozenImporter` (it should — excluded modules are absent from the archive and from
  `sys.path`), so `MIP_AVAILABLE` is `False` and nothing tries to import it.

Net effect on the bundle: **−pandas −sklearn −mip, +highspy** ≈ a large reduction, probably
to well under 120 MB. Measure it (§5, step 8) rather than trusting that arithmetic.

Excluding mip means a user who sets `solver_backend = "mip"` (or `mip-cbc` / `mip-highs`) in
their settings file gets a `RuntimeError` from the packaged app — and gets it ten minutes
into a run, not at startup. **Decided: validate the setting.** See §4.5 for what that
validation covers, since the same mechanism covers the diversimax decision in §4.4.

### 4.3 Lazy imports and PyInstaller

Commit `f85e6ff` moved `cvxpy`, `numpy`, `gurobipy`, `highspy`, `mip`, `pandas` and
`sklearn` imports _inside_ the functions that use them. PyInstaller's module graph does
follow function-level `import` statements, so this should be transparent — but it is
exactly the kind of change that produces a `ModuleNotFoundError` only in the frozen build.
The `--self-test` smoke test on all three platforms is the check, and it must run a real
selection (it does).

Watch specifically for `highspy` needing a hook of its own — it is a compiled extension
with data files, and nothing in `_pyinstaller_hooks_contrib` covers it as far as I can
tell. If the Linux self-test fails on it, `collect_dynamic_libs("highspy")` in a small
`hook-highspy.py` is the fix (i.e. we may end up replacing the mip hook rather than
deleting the hooks directory outright).

The existing `module_collection_mode={"cvxpy": "pyz+py"}` workaround should still be needed
— cvxpy 1.9 still lists its own package directory at import time. Leave it.

### 4.4 diversimax

`pandas` and `scikit-learn` are now the `diversimax` extra.
`selection_algorithm = "diversimax"` is one of the five valid values, and a user could put
it in their settings file today and have it work. After the bump, without the extra, they
get `RuntimeError("Diversimax algorithm requires the optional 'diversimax' dependencies")`.

**Decided: this app does not need to support diversimax.** So: no `diversimax` extra,
45 MB of pandas + sklearn stays out of the binary, and `selection_algorithm = "diversimax"`
becomes an unsupported value — validated at settings-load time along with the mip backends,
per §4.5.

### 4.5 Settings this build cannot honour, and where to say so

Those two decisions leave the app in a position the library can't help with: two settings values are
syntactically valid to `sortition-algorithms` but unsupported by *our build*, because we
deliberately don't ship the code behind them.

- `solver_backend` in `("mip", "mip-cbc", "mip-highs", "mip-gurobi")` — mip is excluded
  from the bundle (§4.2)
- `selection_algorithm = "diversimax"` — pandas/sklearn are not installed (§4.4)
- (already true today, and worth folding in while we're here:
  `selection_algorithm = "leximin"` needs Gurobi, which we have never shipped. The library
  falls back to maximin with a report line, so this one is informational, not fatal.)

`SettingsHolder` is the right home: it already loads once, caches, and reports into a log
section next to whatever the user just did. Add a check after `Settings.load_from_file`
that inspects the two fields and returns a clear message —
_"solver_backend 'mip' is not available in this build; supported values are: highspy"_ —
rather than letting the run get most of the way through and then die. Unit tests go in
`tests/unit/test_settings_holder.py`, which already has the settings-file-error shape to
copy.

Deliberately a **refusal at load, not a silent rewrite**: quietly swapping the user's
solver for a different one would make two machines with the same settings file produce
selections by different algorithms without saying so. That is exactly the kind of thing this
app must never do.

### 4.6 The macOS x86_64 pin — now removable, but later

`strat-select.spec` has `target_arch="x86_64"` with the comment _"python-mip has no arm64
macOS wheel"_, and `build-executables.yml` runs the macOS job on `macos-13` with a `TODO`
noting GitHub has been retiring those runners. Both constraints exist because of mip.

With mip excluded, and `highspy` shipping `macosx_11_0_arm64` wheels (and `cbcbox` now
shipping `macosx_15_0_arm64` too, if we ever wanted mip back), **the macOS build can go
native arm64 on a modern runner.** That would fix the "won't work on newer ARM Macs without
Rosetta" note in the workflow, which is the majority of Macs SF staff will be using.

**Decided: leave the macOS work until later.** Not in this PR. It is a genuinely separate
change with its own risk — a new runner, a new architecture, and no ARM Mac in CI to test
the _result_ beyond `--self-test` — and this PR is already doing enough. Two things to carry
forward so it doesn't get lost:

- say in this PR's description that the x86_64 pin is now unblocked, and leave the
  `target_arch="x86_64"` comment in the spec updated to say _why_ it is still there (habit
  and caution, not mip);
- the `macos-13` runner retirement is a clock we don't control. If GitHub pulls it, this
  stops being a nice-to-have and becomes the thing blocking macOS builds entirely.

---

## 5. The work, in order

Ordered so the risky parts happen under test, and so each step's failure mode is legible.

### Step 1 — bump the pin, run the suite, change nothing else

```
uv add "sortition-algorithms==0.12.10"
just test
```

Expected: the three `"Trial number: 1"` assertions in §2.3 fail. **Anything else that goes
red is new information and belongs in this document before it gets fixed.** Do not fix
anything in this step; record what broke.

Also run `just check` — `mypy` may have opinions about the newly-lazy imports or the
`progress_reporter: Any` annotation.

### Step 2 — fix the tests that the retry-loop move broke

- `tests/integration/test_threaded_selection.py`: swap `"Trial number: 1"` for
  `"Using maximin algorithm"` in both tests; in `test_the_library_log_arrives_while_the_selection_runs`
  collapse the now-redundant pair of assertions into one.
- `tests/e2e/test_csv_flow.py:93`: same swap.
- Update the docstring at `test_threaded_selection.py:82` — it says "The trial and algorithm
  lines", and there are no trial lines any more.
- Update the comment at `strat_app/qt/workers.py:127` ("which trial it is on, which
  algorithm it picked") for the same reason.

Green here means the bump is behaviourally clean for the CSV path.

### Step 3 — packaging

- `EXCLUDES += ["mip", "cbcbox"]` in `strat-select.spec`.
- Delete `pyinstallerhooks/hook-mip.py`; remove `hookspath` if the directory ends up empty
  (keep it if `highspy` turns out to need a hook, §4.3).
- Update the two stale comments in the spec that reference the mip hook.
- `uv run pyinstaller strat-select.spec && ./dist/strat-select-linux --self-test`, and
  record the size. Then let CI do Windows and macOS.
- If the frozen build fails to import `highspy`, add `pyinstallerhooks/hook-highspy.py`.

Doing this _before_ the progress bar means a red self-test can only be about the bump, not
about new app code.

### Step 4 — refuse the settings this build cannot honour

Per §4.5, and red-first: `tests/unit/test_settings_holder.py` gets cases for a settings file
naming a mip backend and one naming `diversimax`, asserting the returned message says which
value is unsupported and what is supported. Then implement the check in `SettingsHolder`.

Keep it a **message, not an exception** — `init_settings` already returns a string that
`init_settings_log` puts in the log section next to the user's action, and that is exactly
where this belongs. Whether an unsupported value should also block the run button, or just
warn loudly, is worth thinking about while writing the test: my read is **block**, because a
warning that is followed by a ten-minute wait and then a `RuntimeError` is worse than no
warning at all.

### Step 5 — the gsheet path, by hand

The gsheet path has no automated end-to-end coverage (eel-to-qt plan, D6), so this is the
step that needs care. Work the §6.3 checklist from that plan against a scratch spreadsheet:

1. wrong sheet name → sensible error, load button still usable
2. wrong tab name → sensible error naming the tab
3. good sheet → categories and respondents reports match the CSV path for the same data
4. run with "generate remaining tab" on → both output tabs written, dupes highlighted orange
5. `number_selections = 2` → warning shown, no remaining tab, test-panel button refused
6. run twice in a row → output tabs are not clobbered or duplicated

Plus three new cases the bump introduces:

7. a `.xlsx` uploaded to Drive (not converted) → the new `NotNativeGoogleSheetError`
   message appears in the features output area, and the app stays usable
8. a respondents tab with leading/trailing whitespace in a header cell → now loads
   (previously a parse error)
9. a respondents tab with a numeric-looking header cell → now loads

Item 6 remains the one to be most careful about — it exercises `find_unused_tab_suffix`,
which is unchanged, but "unchanged code, changed surroundings" is exactly how this kind of
thing bites.

### Step 6 — `QtProgressReporter`, red-first

New module `strat_app/qt/progress.py`:

- a `QObject` with `phase_started = Signal(str, object, str)` (name, total-or-None,
  message), `progress = Signal(int, str)`, `phase_ended = Signal()`;
- `start_phase` / `update` / `end_phase` emit them; connections are
  `Qt.ConnectionType.QueuedConnection` so they land on the GUI thread;
- throttling: `time.monotonic()`, `min_interval_seconds = 0.1` (≈10 Hz), **phase
  transitions always flush** (`force=True`), so the label never lags behind the bar;
- also flush the last `update` on `end_phase`, so a phase never visually stops at 187/200.

Tests (`tests/integration/test_progress.py`):

- `qtbot.waitSignal` on `phase_started` asserts name/total/message arrive intact, including
  `total is None` for the convergence loops;
- hammer `update()` in a tight loop (say 1000 calls with no sleep) and assert the emitted
  signal count is bounded — this is the test that stops a future refactor from
  reintroducing the flood;
- assert a `start_phase` immediately following an `update` is _not_ throttled away;
- assert `end_phase` emits the final value.

Then wire it: `CsvSession.progress_reporter` and `GSheetSession.progress_reporter` already
exist as `Any = None` placeholders and are already passed through to `run_stratification`
via the `**extra` dance in `_stratify`. Replace the placeholder with a real type and delete
the `extra = {...} if ... else {}` conditional — 0.12 takes `progress_reporter=None`
happily, so it can be passed unconditionally. Drop the "the library grows a
progress_reporter argument in 0.12" comments in both sessions.

The view protocols in `strat_app/sessions/view.py` gain a method — something like
`set_progress(current: int, total: int | None, message: str)` alongside `set_busy` — so the
sessions stay Qt-free and `CallRecorder` keeps working unchanged.

### Step 7 — the `QProgressBar` itself

`csv_tab.py:93-97` and `gsheet_tab.py:127-131` both have a `busy_bar` with
`setRange(0, 0)` and the comment _"no phases or percentages from the library at this
version, so all we can honestly show is that something is happening"_. That comment can
finally go.

- `total is None` → `setRange(0, 0)` (busy), else `setRange(0, total)` + `setValue(current)`;
- a `QLabel` under the bar for `message`;
- `set_busy(True)` should reset the bar to indeterminate with an empty label, so a second
  run doesn't briefly show the first run's final state.

**Decided: duplicate the code across the two tabs** rather than extracting a shared
`ProgressPanel` widget. They already duplicate `set_busy`, `set_panel_size_range`,
`set_panel_size`, `set_run_enabled` and `_row`, so the progress panel is one more symptom of
a duplication that predates this work — and the right time to fix that is in a refactor
aimed at it, not inside a version bump. Noted in §7 as its own piece of work.

### Step 8 — re-measure, re-smoke, and write it up

- Record the before/after bundle size for all three platforms in the PR description.
- Re-run the packaged `--self-test` everywhere (CI does this already).
- Update `README.md` if it names the library version anywhere.

---

## 6. Test coverage: what this PR adds and what it can't

Per the no-exceptions policy, all three levels are covered:

- **Unit** — `tests/unit/`: the reporter's throttling logic is pure (`time.monotonic` +
  an interval), so the throttle-bound test can live here with a fake clock, independent of
  Qt. `test_settings_holder.py` gains the unsupported-value cases (step 4).
  `test_gsheet_session.py` gains the test-panel-button case from §2.4. Session-level:
  `progress_reporter` is passed through to `run_stratification` and is not `None`.
- **Integration** — `tests/integration/test_progress.py` (new, §5 step 6) for the
  signal/thread bridge with `qtbot`; extensions to `test_csv_tab.py` /
  `test_gsheet_tab.py` asserting the bar goes determinate when a `total` arrives and busy
  when it doesn't.
- **End-to-end** — `tests/e2e/test_csv_flow.py` gains an assertion that the progress bar
  reached a determinate range during a real `maximin` run (the `multiplicative_weights`
  phase guarantees one), alongside the existing detailed-log assertion.

What it can't cover, and we should be honest about in the PR: the real gsheet round-trip
(§5 step 5 is manual, per the eel-to-qt plan's D6) and the packaged builds beyond
`--self-test`.

---

## 7. Related, but explicitly not in this PR

- **Cancellation.** Still not possible, and 0.12 does not change that. The library wraps
  our reporter in `ErrorSwallowingReporter` _by design_, so raising from `update()` to
  abort a run is swallowed and logged, not propagated. Killing a `QThread` mid-solve isn't
  acceptable. It needs upstream support: `should_cancel() -> bool` on the protocol, or a
  cancellation token argument. You own the repo, so it's cheap to ask — worth an issue
  regardless of whether we take this bump. **This is the single biggest remaining UX gap**:
  after this PR the user can _see_ that a 10-minute run is progressing, but still can't stop
  it.
- **`load_already_selected` / replacements.** A feature for the app, not part of the bump.
  Needs its own UI (a third file input on the CSV tab, a third tab name on the gsheet tab)
  and its own plan. The library side is ready:
  `SelectionData.load_already_selected(settings)` and
  `run_stratification(..., already_selected=people)`.
- **macOS arm64** — decided, deferred: §4.6.
- **Relaxing `requires-python`.** The library dropped its `<3.13` cap in 0.12 and now
  advertises 3.13 and 3.14. This app still says `>=3.11,<3.13`. Nothing forces us to move,
  and PySide6 + PyInstaller are the constraint that actually matters, so: separate change,
  separate PR, only if there's a reason.
- **Shared widget code across the two tabs.** They duplicate `set_busy`,
  `set_panel_size_range`, `set_panel_size`, `set_run_enabled`, `_row`, and — after step 7 —
  the progress panel. Decided (§5 step 7) to duplicate rather than extract for now, so this
  becomes a tidy-up of its own. Do it as a refactor aimed at the duplication, with the tab
  integration tests as the safety net; not inside a bump.
- **Configurable output tab names on the gsheet tab.** Considered and dropped for this
  round. Worth recording _why_, since the trail is confusing: the `selected_tab_name` /
  `remaining_tab_name` assignments the Eel app made (`script.py:455-456` at `f5de19a^`) and
  the port dropped were **dead code even when they were there** — they were set to the
  library's own default strings, and the library never reads those attributes anyway
  (`write_selected` _assigns_ them with the title of the tab it just created,
  `adapters.py:843`). So nothing regressed in the port and there is nothing to restore. If
  we ever do want user-chosen tab names, the knob is
  `data_source.tab_namer.selected_tab_name_stub`, applied in `_write_output` — see
  `llm-working/upstream.md` issues 3 and 4 for the two API sharp edges that would need
  handling first.
- **Upstream issues.** Written up in `llm-working/upstream.md` for you to file: the
  `ConfigurationError` escape (§2.4), `should_cancel()` on `ProgressReporter` (above), the
  stale `DEFAULT_SETTINGS` comment (§2.5), and the vestigial
  `GSheetDataSource.selected_tab_name` / `remaining_tab_name` write-only attributes (§2.1).

---

## 8. Decisions

Answered by Chewie, and folded into the sections above.

| Decision                                                                                                 | Where it lands  |
| -------------------------------------------------------------------------------------------------------- | --------------- |
| This app does not need to support diversimax — no extra, 45 MB of pandas + sklearn stays out             | §4.4, §4.5      |
| Validate `solver_backend` (and `diversimax`) at settings-load time rather than failing mid-run            | §4.5, §5 step 4 |
| Leave the macOS arm64 work until later; note in the PR that it is now unblocked                          | §4.6            |
| Test-panel button with `number_selections > 1`: disable it in the app **and** raise the upstream issue    | §2.4, upstream 1 |
| Keep the `user_logger` → detailed-log bridge; it says _what_, the bar says _how far_                     | §2.3            |
| `NotNativeGoogleSheetError`: just show the library's message, no app-side special-casing                  | §2.6            |
| gspread `request_timeout`: leave it at the library's 60s default                                          | §2.6            |
| Duplicate the progress panel code across the two tabs rather than extracting a shared widget              | §5 step 7, §7   |
| No configurable output tab names this round — nothing was lost in the port, so nothing to restore         | §7              |
| Upstream issues go in `llm-working/upstream.md`                                                           | `upstream.md`   |

Nothing is left open. The plan is ready to work through.

### One thing worth knowing before anyone reopens the tab-name question

The `selected_tab_name` trail is genuinely misleading and cost time once already. In short:
the Eel app's assignments were dead code even while they were there, so the port didn't
regress anything and there is nothing to restore. The full explanation is in §7 under
"Configurable output tab names", and the two API sharp edges that made it confusing are
written up as upstream issues 3 and 4.
