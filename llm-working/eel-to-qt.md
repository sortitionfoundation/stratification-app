# Migrating the Strat App from Eel to Qt

Status: **agreed plan for a spike**. All open questions answered by Doctor Chewie; the
answers are recorded verbatim in [Decisions](#decisions) at the bottom and folded into the
body above. Nothing implemented yet.

Two answers changed the plan materially:

- **No `sortition-algorithms` bump for this work** (D5) — so no structured progress bar.
  The live detailed log survives anyway; see §5.4.
- **Both tabs in scope**, not just CSV (D10) — §10 rescoped accordingly.

## 1. Recommendation in one paragraph

Rewrite the GUI as **native PySide6 widgets** (no HTML, no embedded browser), and use the
port as the excuse to split `script.py` into a UI-agnostic session layer plus a thin Qt
view layer. Keep PyInstaller for packaging. The interesting work is not "Qt instead of
Chrome" — it is that today every piece of business logic reaches out and calls
`eel.some_js_function(...)` directly, which is why there are zero tests. Introduce a view
protocol at that boundary and the whole app becomes testable without a GUI; the Qt widgets
then become a thin, separately-testable adapter.

## 2. What we have today

Findings from reading the repo:

| Thing                 | Detail                                                                                                                                                                                                                                            |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `script.py`           | 610 lines. Three concerns tangled together: session state (`CSVHandler`, `GSheetHandler`, `SettingsHolder`), view updates (~25 direct `eel.*` calls), and 20 `@eel.expose` entry points.                                                          |
| `web/main.html`       | 253 lines. Bootstrap 5 + jQuery **loaded from CDN** — so the CSV workflow silently needs an internet connection today.                                                                                                                            |
| `web/js/main.js`      | 286 lines, almost all DOM plumbing: `getElementById`, `innerHTML = ...`, `disabled = false`. Nothing worth preserving.                                                                                                                            |
| Tests                 | **None.** `test_stratification.py` and `test_end_to_end.py` were deleted in `1b31e13` ("Move to sortition-algorithms library"), along with `.github/workflows/run-tests.yml`. The test badge in `README.md` is stale.                             |
| Fixtures              | `fixtures/categories_no_flex.csv` exists but is **untracked**. No people fixture. The sibling repo has `tests/fixtures/{features,candidates,candidates_lower}.csv`.                                                                               |
| Build                 | PyInstaller, driven via `python -m eel script.py web ...` in `.github/workflows/build-executables.yml`. `--onefile` on Linux/Windows, `--onedir --windowed --target-arch=x86_64` on macOS (macos-13 runner, x86_64 forced because of python-mip). |
| Current artefact size | `strat-select-linux` 126 MB, `strat-select-win.exe` 111 MB (v1.1.0). The bulk is numpy/cvxpy/mip/highspy, not eel.                                                                                                                                |
| Library pin           | `sortition-algorithms==0.11.5`. Latest tag upstream is **0.12.10**.                                                                                                                                                                               |

### Eel's own README says it plainly

> "This project is effectively unmaintained. It has not received regular update in a number
> of years, and there are no plans by active maintainers for this to change."

Architecturally eel runs a Bottle/gevent webserver on localhost, launches Chrome in app
mode, and serves an `/eel.js` shim that proxies function calls over a websocket. So the app
currently depends on: an unmaintained library, a gevent-patched event loop, a locally bound
TCP port, a separately-installed Chrome/Edge, and a CDN. That is a lot of moving parts for
two tabs of form controls.

### The maintainability problem is deeper than eel

`CSVHandler._set_panel_size` has this:

```python
# finally update the display - unless we've been called from the JS
# in which case skip this to avoid infinite loops.
if update_eel:
    eel.set_csv_panel_size(self.panel_size_str)
```

That `update_eel` flag exists purely because the panel size is a free-text `<input>` whose
value is round-tripped through Python. A `QSpinBox` with `setRange(min, max)` deletes the
flag, the string parsing, the `panel_size_str` / `panel_size_num` pair and the loop-guard —
about 25 lines per handler class, twice. That kind of deletion is the real payoff.

## 3. Options considered

### Option A — QWebEngineView + QWebChannel (keep the HTML, swap the bridge)

Keep `web/main.html` verbatim, replace `eel.js` with `qwebchannel.js`, expose a `QObject`
with slots instead of `@eel.expose`.

- Cheapest in raw diff size, and a well-trodden Qt path.
- But: still two languages, still a message-passing bridge, still CDN assets, and it adds
  a ~130 MB Chromium (`QtWebEngineCore`) to a binary that is already 126 MB.
- Fixes the "unmaintained upstream" problem and nothing else.

**Rejected** — and you've since confirmed you want no HTML left, which settles it.

### Option B — Native Qt Widgets (PySide6) — **recommended**

Rewrite the UI as `QMainWindow` / `QTabWidget` / ordinary controls.

- One language. Standard, boring, extremely well documented technology.
- Testable headlessly with `pytest-qt` + `QT_QPA_PLATFORM=offscreen`.
- No CDN, no localhost port, no browser dependency, no gevent.
- Native `QFileDialog` for input _and_ output, replacing the `data:` URI download hack.
- Opens the door to a real progress bar (see §5.4), which the current UI cannot do.
- Cost: the UI is genuinely rewritten. But it is ~250 lines of HTML implementing two forms.

### Option C — Qt Quick / QML

Declarative UI in yet another language, with worse packaging ergonomics and no benefit for
a form-heavy app. **Rejected.**

### PySide6 or PyQt6?

**PySide6.** It is the Qt Company's official binding, LGPL-3 (so no licence question ever
arises for downstream users), and tracks Qt releases. The repo is GPL-3 so PyQt6's GPL
would also be legally fine here, but there is no upside. Depend on **`PySide6-Essentials`**
rather than the `PySide6` meta-package — that alone keeps QtWebEngine and the addons out of
the wheel set and therefore out of the bundle. **Agreed (D1).**

## 4. Mapping the existing UI to widgets

| Today (HTML)                                                          | Proposed widget                                                                                                 |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `<input type=file id=csv-file-features>`                              | `QPushButton` "Choose categories CSV…" → `QFileDialog.getOpenFileName`, plus a `QLabel` showing the chosen path |
| `<input type=file id=csv-file-people>` (disabled until features load) | same, `setEnabled(False)` until features load                                                                   |
| `#csv-output-area-features-target-p` (`innerHTML`)                    | `QTextBrowser` (read-only; rendering settled in §5.5)                                                           |
| `#csv-panel-size` text input + Python-side validation                 | `QSpinBox` with `setRange(min_selection, max_selection)`                                                        |
| `#csv-run-btn` / `#csv-run-test-btn`                                  | `QPushButton` ×2                                                                                                |
| `#csv-download-selected-btn` (`data:` URI)                            | `QPushButton` "Save selected…" → `QFileDialog.getSaveFileName`                                                  |
| `#g-sheet-name`, `#g-sheet-respondents-tab`, `#g-sheet-features-tab`  | `QLineEdit`                                                                                                     |
| `#g-sheet-gen-rem-tab` checkbox                                       | `QCheckBox`                                                                                                     |
| `#g-sheet-number-selections`                                          | `QSpinBox` (min 1)                                                                                              |
| Bootstrap collapse "advanced settings"                                | checkable `QGroupBox`                                                                                           |
| Bootstrap collapse "detailed log"                                     | checkable `QGroupBox` containing a `QTextBrowser`                                                               |
| `#user-alerts` div                                                    | `QStatusBar` message, or `QMessageBox` for errors                                                               |
| `logo_sortition-foundation_alt.svg`                                   | `QSvgWidget` (needs `PySide6.QtSvg`, which is in Essentials)                                                    |
| tabs                                                                  | `QTabWidget`                                                                                                    |

Two deliberate behaviour changes fall out of this, both **agreed (D4)**:

1. **Output is saved via a Save dialog** rather than "downloaded". This also means the CSV
   path can switch from `CSVStringDataSource` to `CSVFileDataSource` and stop passing whole
   files around as strings.
2. **Panel size becomes a spin box** clamped to the feasible range, so it is impossible to
   type a value outside `[min_selection, max_selection]`.

Beyond those two, **the layout, wording and flow stay as they are (D11)**. The widget tree
mirrors the current page: same two tabs in the same order, same step numbering, same labels,
same collapsible advanced-settings and detailed-log sections. This is a port, not a
redesign. It also keeps the port reviewable — if a screen looks different, that's a bug.

## 5. Target architecture

### 5.1 Layout

```
strat_app/
  __init__.py
  __main__.py            # QApplication + MainWindow; `uv run python -m strat_app`
  settings_holder.py     # SettingsHolder, unchanged logic
  sessions/
    view.py              # CsvView / GSheetView / LogView protocols — no Qt import
    csv_session.py       # CSVHandler, de-eel-ed — no Qt import
    gsheet_session.py    # GSheetHandler, de-eel-ed — no Qt import
    log.py               # GuiLog
  qt/
    main_window.py
    csv_tab.py           # implements CsvView
    gsheet_tab.py        # implements GSheetView
    log_panel.py         # implements LogView
    report_view.py       # RunReport -> widget
    workers.py           # QThread worker, progress reporter, log bridge
tests/
  unit/                  # no Qt, no network
  integration/           # pytest-qt, offscreen
  e2e/                   # whole app, offscreen
  fixtures/
```

`script.py` goes away. The PyInstaller entry point becomes a two-line `main.py` (PyInstaller
is happier with a plain script than with `-m`). **Package restructure is in scope (D2).**

### 5.2 The view protocol — the crux of the whole plan

Every `eel.*` call in `script.py` becomes a method on a protocol. This is a near-mechanical
transformation; the current calls _are_ the protocol:

```python
class CsvView(Protocol):
    def show_features_report(self, report: RunReport) -> None: ...
    def show_people_report(self, report: RunReport) -> None: ...
    def set_panel_size_range(self, minimum: int, maximum: int) -> None: ...
    def set_panel_size(self, size: int) -> None: ...
    def set_people_input_enabled(self, enabled: bool) -> None: ...   # enable_csv_selection_content
    def set_run_enabled(self, enabled: bool) -> None: ...            # enable/disable_csv_run_button
    def offer_selected_download(self, contents: str, filename: str) -> None: ...
    def offer_remaining_download(self, contents: str, filename: str) -> None: ...
```

The sessions never import Qt. Tests drive them with a `RecordingView` that appends
`(method, args)` tuples — **agreed as an acceptable test double (D7)**. It is a spy on a
boundary _we_ own, not a fake implementation of an external service, and no "mock mode"
exists in the shipped app.

`GSheetHandler` additionally gains an injected data source (default
`adapters.GSheetDataSource`) so tests can substitute a fixture-backed
`AbstractDataSource` — that's the library's own documented extension point.

### 5.3 Threading — mandatory, not optional

Today `run_selection` blocks; with eel that only wedges the gevent loop and the browser
carries on rendering. In Qt, blocking the main thread **freezes the window**, and a
10-minute leximin run would look like a crash. So:

- `SelectionWorker(QObject)` moved onto a `QThread`. Signals: `progress(...)`,
  `log_line(str)`, `finished(success, report, selected_rows, remaining_rows)`,
  `failed(str)`.
- Google Sheets load/write also goes on the worker thread — `gspread` is blocking network
  I/O and the existing code comments mention multi-second API stalls.
- Rule to hold the line on: the worker touches **no** widget, only emits signals.

### 5.4 Feedback during a run, staying on `sortition-algorithms==0.11.5`

**No library bump in this work (D5)** — we port on the current pin so behaviour is directly
comparable, and revisit 0.12.x separately. That splits what we can offer during a long run
into two halves, and the split is better than I first assumed:

**Available now, at 0.11.5** — the live detailed log. I checked the installed package:
`utils.override_logging_handlers()` is present, and there are 16 `add_line_and_log()` /
`add_message_and_log()` call sites in `core.py` and `committee_generation/`, including the
per-trial `"trial_number"` message. So:

- a `logging.Handler` subclass that emits a Qt signal per record, installed over the
  `sortition_algorithms_user` logger for the duration of the run, gives a detailed log that
  **updates while the selection runs** instead of only at the end. That alone is better
  feedback than the current app gives, and it costs no version bump.

**Deferred to the bump** — the structured progress bar. `ProgressReporter` (`start_phase` /
`update` / `end_phase`, documented in the library's `docs/progress.md`) landed *after*
0.11.5, so there's no phase/percentage data to drive a determinate `QProgressBar`. For now:
an **indeterminate** `QProgressBar` (busy indicator) plus the existing
`"Selecting... please wait..."` line, shown while the worker runs and hidden when it
finishes. Same information the user gets today, but on a window that stays responsive.

Design the seam for it now, though: the worker takes an optional `progress_reporter`
argument it currently never populates, so adding `QtProgressReporter` after the bump is a
one-file change rather than a re-plumb.

**Cancellation is out of reach either way.** The library deliberately swallows exceptions
raised by a reporter, so Cancel cannot be implemented by raising from one, and killing a
`QThread` mid-solve is not acceptable. Proper cancellation needs upstream support — a
`should_cancel()` on the protocol, or a cancellation token. Worth an issue on
`sortition-algorithms`; you own it, so that's cheap. Out of scope here.

When we do take the bump, note it is not free: 0.12 also brings `GSheetTabNamer` and
`load_already_selected`, and the current code assigns `data_source.selected_tab_name`
directly, which may no longer be the right API. That's its own PR with its own tests —
outlined separately in [`llm-plans/library-bump.md`](../llm-plans/library-bump.md).

### 5.5 Rendering reports without HTML

`RunReport.as_html()` produces a small subset: `<b>`, `<b style="color: red">`, `<br />`,
and `tabulate(..., tablefmt="html")` tables. `QTextBrowser` renders all of that natively —
Qt's rich text engine, not a browser. Three choices were on the table:

- **(a)** Feed `report.as_html()` to `QTextBrowser.setHtml()`. Simplest, keeps bold/red/tables.
  Technically "HTML" but it is library-generated markup into a text widget, with no web
  engine, no DOM, no JS.
- **(b)** Feed `report.as_text()` to a `QPlainTextEdit`. Zero HTML, but loses the CRITICAL
  red highlighting that flags infeasible targets.
- **(c)** Walk the structured report (`RunReport.serialize()`, or a small public accessor
  added upstream) and render lines with `QTextCharFormat` and tables as `QTableWidget`.
  Purest, best-looking, most work, probably wants a tiny upstream API addition.

**(a) for now (D3)**, with (c) as a possible follow-up. Worth being precise about what this
means for the "no HTML left" aim: no HTML *page*, no hand-written markup, no browser engine
and no JS survive the port. The only remaining HTML is a string the library hands us, going
straight into a Qt rich-text widget. Isolating it in `report_view.py` means swapping to (c)
later touches one module.

## 6. Testing strategy

Nothing in this repo is tested today, so the port has to bring its own safety net — and the
net has to exist _before_ the logic moves, or we have no way to know the port preserved
behaviour.

Tooling: `pytest`, `pytest-qt`, `pytest-cov`, `QT_QPA_PLATFORM=offscreen` in CI (and
locally). **Add a `justfile`** with `just test` / `just check` mirroring the
sortition-algorithms repo, and **restore `.github/workflows/run-tests.yml`** — both
**agreed (D8)**. The README's test badge starts working again as a side effect.

All three test types from your no-exceptions policy are present: unit (§6.1), integration
(§6.2) and end-to-end (§6.3). The one gap is deliberate and scoped: the Google Sheets path
has no *automated* end-to-end coverage, because there are no CI credentials for it (D6).
Its session logic is still unit-tested against a fixture-backed data source; only the real
API round-trip is manual. See §6.3 for the manual checklist that stands in for it.

### 6.1 Unit tests — sessions with a `RecordingView`, no Qt, no network

`tests/unit/test_csv_session.py`:

- loading a valid categories CSV → view told to show a report, people input enabled
- empty file contents → "was the file empty?" reported, people input **not** enabled
- missing/invalid `sf_stratification_settings.toml` → error surfaced, load aborted
- features where `min_selection == max_selection` → panel size auto-set to that value
- features loaded → `set_panel_size_range(min, max)` called with values from
  `features.minimum_selection` / `maximum_selection`
- reloading categories after people are loaded → people are re-parsed against new features
- run button enabled **only** when features **and** people **and** size > 0 (table-driven
  over the eight combinations)
- successful run → report shown, both downloads offered, contents parse as CSV with the
  expected header and row count
- infeasible targets → "No panels written…" and no downloads offered
- exception mid-selection → error reported, session still usable afterwards

`tests/unit/test_gsheet_session.py` (fixture-backed `AbstractDataSource`, no network):

- blank sheet name → "Please enter a spreadsheet name…", load button stays disabled
- entering a name → load button enabled, previous state cleared
- changing the categories tab name resets features **and** people; changing the respondents
  tab name resets people only (this asymmetry is real in the current code and easy to break)
- `number_selections > 1` → warning emitted and `gen_rem_tab` forced false
  (`_safe_gen_rem_tab`)
- a `gspread.exceptions.APIError` during load → the specific "API error causing delay"
  message, and `KnownFailureError` handling does not double-report

`tests/unit/test_settings_holder.py`, `tests/unit/test_gui_log.py`:

- settings loaded once and cached; failure reported once per section
- log accumulation, `reset`, blank-line filtering, per-section isolation

### 6.2 Integration tests — widgets with `qtbot`

`tests/integration/`:

- each tab satisfies its view protocol: call `set_run_enabled(False)` → both buttons
  actually disabled; `set_panel_size_range(20, 24)` → spin box `minimum()`/`maximum()` match
- user actions raise the right session calls: `qtbot.mouseClick(run_btn, LeftButton)` with a
  recording session → `run_selection(test_selection=False)` recorded
- `QSpinBox` change → session's panel size updated → run button state recomputed
- report rendering: a `RunReport` containing a table and a CRITICAL line → widget's
  `toPlainText()` contains the table cells; the critical text is present
- worker thread: `qtbot.waitSignal(worker.finished, timeout=...)` around a real (small)
  selection using fixtures; assert the busy indicator is shown on start and hidden on
  finish, and that the worker touched no widget off-thread
- log bridge: with the handler installed over `sortition_algorithms_user`, a record emitted
  from the worker thread reaches the log panel — and the handler is removed again afterwards
  so a second run doesn't double-log
- tab wiring: `MainWindow` has both tabs with the expected titles; log panel collapses

### 6.3 End-to-end tests

`tests/e2e/test_csv_flow.py` — real `MainWindow`, real `sortition_algorithms`, offscreen:

1. drive "choose categories file" with a fixture path (via the seam described in §7),
2. then the people file,
3. assert the reports and that the spin box is now bounded and pre-filled,
4. click Run, `qtbot.waitSignal(finished)`,
5. save both outputs to `tmp_path`,
6. assert the selected CSV has exactly `panel_size` data rows, that every ID appears in the
   input pool, and that selected + remaining partition the pool.

`tests/e2e/test_gsheet_tab.py` — the same *widget* flow, but against a fixture-backed
`AbstractDataSource` injected into the session, so it runs everywhere with no credentials.
It proves the tab, the worker and the wiring; it does not prove gspread.

**No automated test against the real Google API (D6).** The gspread round-trip is verified
by hand before the branch merges, against a scratch spreadsheet, working through this
checklist:

1. wrong sheet name → sensible error, load button still usable
2. wrong tab name → sensible error naming the tab
3. good sheet → categories and respondents reports match the CSV path for the same data
4. run with "generate remaining tab" on → both output tabs written, dupes highlighted orange
5. `number_selections = 2` → warning shown, no remaining tab, test-panel button refused
6. run twice in a row → output tabs are not clobbered or duplicated

If we later want this in CI, it needs a service-account JSON in GitHub secrets and a
throwaway sheet — parked, not forgotten. It is the largest known hole in the safety net, so
step 2's characterisation tests matter more for the gsheet path than for the CSV one.

### 6.4 Packaged-binary smoke test — new, and overdue

CI builds three binaries today and never runs any of them. The classic PySide6 packaging
failure ("could not load the Qt platform plugin") only ever shows up in the packaged
artefact. So: add a `--self-test` flag that constructs the `QApplication` and `MainWindow`,
pumps the event loop briefly, and exits 0. Then in each build job run the freshly built
artefact with `--self-test` (under `xvfb-run` on Linux). Cheap, and it would catch the one
class of bug that currently reaches users first.

## 7. How I'd do it: red/green, step by step

Being straight about the terminology: some of this is genuine red-first TDD (all the new
code), and some is characterisation testing (pinning down behaviour that already exists).
Both matter here; I'll say which is which rather than pretending it's all one thing.

There is one seam I need for testability up front: **file choosing must be separable from
file dialogs.** So `CsvTab.load_features_file(path: Path)` does the work and the button's
slot is only `path = QFileDialog.getOpenFileName(...); self.load_features_file(path)`.
Tests call the method; nobody tries to automate a native dialog.

### Step 0 — test harness (red → green, deliberately)

Add `pytest`, `pytest-qt`, `justfile`, CI `run-tests.yml` (which was deleted and never
replaced). Prove the harness works by committing a test that asserts something false, watch
CI go **red**, fix it to **green**, delete it. Also commit the fixtures: `fixtures/` is
untracked, and we need a people CSV to go with `categories_no_flex.csv` — the sibling
repo's `tests/fixtures/candidates.csv` is the obvious donor.

### Step 1 — characterisation tests against the _current_ eel code (red → green)

Before changing a line of logic, `monkeypatch.setattr(script, "eel", Recorder())` and
assert the exact sequence of view calls for each user action, writing the expectation from
reading the code _first_.

This is the step people skip, and it's the one that pays. Every test written this way is
either green immediately (the code does what I read it to do) or red (it doesn't — and I've
found a real bug, or a real misunderstanding, before porting it). Either outcome is useful;
a green-on-first-run test here is not a wasted test, it is a locked-in behaviour.

The resulting recorded call sequences become the literal specification for the view
protocol in step 2.

### Step 2 — extract the session layer (refactor under green tests)

Create `strat_app/sessions/`, move the handler classes across, replace every `eel.*` call
with a view-protocol call. Port the step-1 tests to the `RecordingView` — same assertions,
new double.

To keep the app runnable and comparable during this step, write a ~40-line `EelCsvView` /
`EelGSheetView` adapter implementing the protocols with the current `eel.*` calls. The eel
app keeps working, so we can run old and new side by side and eyeball them. Both adapters
get **deleted** in step 6.

Red/green here is "tests stay green while the code moves" — if they go red, the extraction
was wrong.

### Step 3 — Qt widgets, one at a time (genuine red-first)

Each of these is: write the failing test, watch it fail for the right reason, implement.

1. `MainWindow` exists with two tabs of the expected titles.
2. `CsvTab` has the expected widgets and correct initial enabled/disabled states.
3. `CsvTab` satisfies `CsvView` — one test per protocol method, asserting widget state.
4. `CsvTab` emits the right session calls on user interaction (recording session double).
5. `GSheetTab` likewise (including the advanced-settings group box).
6. `LogPanel` likewise.
7. `report_view` rendering.

### Step 4 — threading (red-first, `waitSignal`)

Worker + signals, then the busy indicator and the `user_logger` → log-panel bridge (§5.4 —
both work at the current library pin). Tests use `qtbot.waitSignal` and assert on signal
ordering and payloads. Leave the unused `progress_reporter` seam in the worker for the
later bump.

### Step 5 — wire it together and write the e2e tests

`__main__.py`, then the end-to-end tests from §6.3. Realistically some of these are
written red _before_ the wiring, because they define what "wired" means.

### Step 6 — delete eel

Remove `script.py`, `web/`, the eel adapters, the `Eel` dependency, the eel mypy override
in `pyproject.toml`. Update `README.md` and `docs/index.md`. This is the commit where the
"no HTML left" aim is verifiable: `rg -i '<html|innerHTML|eel\.' ` returns nothing.

### Step 7 — packaging and CI

Spec file, three-platform builds, `--self-test` smoke test, size measurement (§8).

Each step is one commit, with `just test` and `just check` green before it lands.

## 8. Packaging

**Recommendation: stay on PyInstaller**, but replace the `python -m eel script.py web ...`
wrapper with a checked-in `strat-select.spec`. The hard part of this build has never been
the GUI toolkit — it's `mip` (hence `pyinstallerhooks/hook-mip.py`), `highspy` and `cvxpy`.
That work is done and shouldn't be thrown away for a toolkit swap. PySide6 is PyInstaller's
best-supported GUI framework and has a maintained hook.

Size control, in priority order:

1. depend on `PySide6-Essentials`, not `PySide6` (keeps QtWebEngine and the addons out
   entirely — QtWebEngineCore alone is ~130 MB);
2. explicitly `excludes=[...]` the Qt modules we don't use in the spec;
3. consider `--onedir` + a zip on Windows/Linux instead of `--onefile`; onefile has to
   extract the whole bundle to a temp dir on every launch, and Qt makes the bundle bigger.

Expect roughly 150–180 MB versus today's 126 MB. Worth measuring early — it's part of the
spike exit criteria.

Alternatives, since you said they're on the table:

| Tool                    | Verdict                                                                                                                                                                                                                                                                                                                                                          |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **pyside6-deploy**      | Qt's own tool, Nuitka-based. Attractive on paper (Qt-official, smaller output) but no cross-compilation, much less mileage with the numpy/cvxpy/mip/highspy stack, and we'd re-solve the mip hook problem in a new tool's idiom. _(I could not get the Qt docs page to render for verification — treat my description as needing a check before relying on it.)_ |
| **Briefcase** (BeeWare) | The best story for signed/notarised macOS `.dmg` and Windows MSI installers. If Gatekeeper warnings are a support burden for you, this is the one to revisit. More project ceremony, and again the scientific stack needs proving.                                                                                                                               |
| **Nuitka** direct       | Smaller and faster-starting binaries, much slower builds, more fragile with C-extension-heavy stacks.                                                                                                                                                                                                                                                            |
| **cx_Freeze**           | No advantage over PyInstaller here.                                                                                                                                                                                                                                                                                                                              |

**PyInstaller it is (D9)** — Briefcase is not being evaluated as part of this work, and
stays on the shelf for if and when macOS signing becomes the pain point.

Two build issues that exist independently of Qt but will bite during this work:

- The macOS job runs on `macos-13` for x86_64 (forced by python-mip). GitHub has been
  retiring macOS 13 runners — worth checking before we depend on that job.
- PySide6 macOS wheels are `universal2` (e.g. `pyside6_addons-6.10.1-cp39-abi3-macosx_13_0_universal2.whl`),
  so an x86_64-only app bundle needs thinning or an explicit `--target-arch`; also note the
  wheel's `macosx_13_0` floor.

## 9. Risks

| Risk                                                            | Mitigation                                                                                                                        |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Packaged binary fails to find Qt platform plugins (the classic) | `--self-test` smoke test run against the built artefact in CI on all three OSes (§6.4)                                            |
| Bundle grows to ~180 MB                                         | `PySide6-Essentials`, module excludes, consider onedir                                                                            |
| Behaviour drift during the port                                 | Characterisation tests (step 1) written before any logic moves; eel adapter kept alive through step 5 for side-by-side comparison |
| Long selections freeze the UI                                   | Worker thread from step 4; no widget access off-thread                                                                            |
| **Google Sheets path has no automated end-to-end coverage**     | Accepted (D6). Session logic unit-tested against a fixture data source; real API verified by the manual checklist in §6.3         |
| No progress bar during long runs, since we're not bumping (D5)  | Indeterminate busy indicator plus the live `user_logger` log, both of which work at 0.11.5 (§5.4); reporter seam left in place    |
| Qt unfamiliarity in the team                                    | The widget set here is entry-level Qt; the spike will show whether that holds                                                     |
| macos-13 runner retirement                                      | Check now, independent of this work                                                                                               |

## 10. Spike scope and exit criteria

**Both tabs (D10)** — CSV and Google Sheets — plus packaging. Ship it as a branch, not a
release, and judge it before merging.

That said, build it **CSV-first**: the CSV path exercises every hard part (view protocol,
widgets, worker thread, file dialogs, PyInstaller with Qt) and is fully testable without
credentials. Get it packaged and running on all three platforms *before* starting the
gsheet tab. If the packaging or size answers come back bad, we find out having written one
tab, not two. Same total scope, cheaper failure mode.

Call the spike a success if:

1. both flows work end to end in a packaged binary on Linux, macOS and Windows — CSV
   automatically, gsheet by the §6.3 manual checklist;
2. `just test` runs unit + integration + e2e green in headless CI on all three platforms;
3. the packaged size is under ~200 MB and startup is under ~5 s;
4. all session logic has moved out of `script.py` into classes with no `eel` import and no
   Qt import, with tests that would have caught a regression in each;
5. `rg -i '<html|innerHTML|eel\.|bootstrap' ` over the repo comes back empty — the "no HTML
   left" aim, made checkable;
6. we can read `csv_tab.py` and `gsheet_tab.py` and agree they are simpler than the
   `main.html` + `main.js` + eel plumbing they replace.

If (3) fails, that's a real answer too, and worth knowing.

## Decisions

Answers from Doctor Chewie, recorded as given. Each is referenced from the body above as
**D1**, **D2** …

| #       | Question                                                    | Decision                                                                                        |
| ------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| **D1**  | PySide6 vs PyQt6; `PySide6-Essentials`?                     | "I agree with the recommendation" — PySide6, Essentials-only.                                   |
| **D2**  | `strat_app/` package restructure in scope?                  | "Yes, package refactor is in scope"                                                             |
| **D3**  | Report rendering (a) / (b) / (c)?                           | "Yes, just (a) for now" — `as_html()` into `QTextBrowser`, isolated in `report_view.py`.        |
| **D4**  | Save dialogs and a clamped `QSpinBox`?                      | "Yes, go ahead with those changes"                                                              |
| **D5**  | Bump `sortition-algorithms` before or after?                | "No bump for initial work, we'll do it later." — stay on 0.11.5; outline in `llm-plans/library-bump.md`. |
| **D6**  | Google Sheets credentials for CI?                           | "For spike we will live without automated tests." — manual checklist in §6.3 instead.           |
| **D7**  | `RecordingView` / fixture data source vs the no-mocks rule? | "Test doubles you suggest are fine."                                                            |
| **D8**  | Add a `justfile` and restore `run-tests.yml`?               | "Yes to both."                                                                                  |
| **D9**  | PyInstaller or evaluate Briefcase?                          | "Stick to PyInstaller."                                                                         |
| **D10** | CSV tab only, or both?                                      | "Let's port both tabs" — built CSV-first, see §10.                                              |
| **D11** | Any UI complaints to fix while rebuilding?                  | "The UI is good enough, so no changes in this work"                                             |

### What follows from D5 and D10

- **D5** costs us the determinate progress bar and gains us a directly comparable port. The
  live detailed log is *not* lost — `override_logging_handlers()` and 16 `*_and_log()` call
  sites are already in the pinned 0.11.5, so the log streams during a run (§5.4). The
  worker keeps an unused `progress_reporter` argument so the bar is a one-file addition
  after the bump. The bump itself is outlined in `llm-plans/library-bump.md`.
- **D10** plus **D6** means the gsheet tab is the riskiest part of the port: most surface
  area, least automated coverage. Mitigation is to lean harder on step 1's characterisation
  tests there, and to keep the eel adapter alive until the manual checklist passes so old
  and new can be run side by side against the same spreadsheet.

### Still open

Nothing blocking. Two things to check before the packaging step, neither caused by this
work:

- whether the `macos-13` runner (x86_64, forced by python-mip) is still available;
- how PySide6's `universal2` macOS wheels interact with the forced `--target-arch=x86_64`.

## Sources

- [Eel README](https://github.com/python-eel/Eel) — "effectively unmaintained"
- [PyQt6 vs PySide6 licensing](https://www.pythonguis.com/faq/licensing-differences-between-pyqt6-and-pyside6/)
- [PySide vs PyQt in 2026](https://docs.bswen.com/blog/2026-04-02-pyside-vs-pyqt-licensing/)
- [pytest-qt documentation](https://pytest-qt.readthedocs.io/en/latest/intro.html)
- [Headless testing of PySide/PyQt apps with pytest-qt](https://ilmanzo.github.io/post/testing_pyside_gui_applications/)
- [Qt for Python deployment](https://doc.qt.io/qtforpython-6/deployment/index.html)
- [PyInstaller changelog — QtWebEngine / PySide6 bundle handling](https://pyinstaller.org/en/v6.16.0/CHANGES.html)
- [QtWebEngineCore size discussion](https://github.com/orgs/pyinstaller/discussions/7322)
- [PyQt/PySide packaged installer file sizes](https://www.pythonguis.com/faq/packaged-installer-file-sizes/)
- [Packaging PySide6 for macOS with PyInstaller](https://www.pythonguis.com/tutorials/packaging-pyside6-applications-pyinstaller-macos-dmg/)
- [PySide6 6.10.1 macOS universal2 wheel](https://download.qt.io/official_releases/QtForPython/pyside6-addons/)
- `sortition-algorithms` `docs/progress.md` and `docs/adapters.md` (local checkout)
