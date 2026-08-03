# Bumping `sortition-algorithms` 0.11.5 → 0.12.x

Status: **outline only, parked.** Deliberately deferred out of the Eel→Qt port (see
`llm-working/eel-to-qt.md`, decision D5) so that port stays a like-for-like comparison.
Do this afterwards, as its own PR. This is a sketch, not a worked plan — it needs the same
research pass the Qt plan got before anyone starts.

## Why do it

Three things, in rough order of value:

1. **Progress reporting.** 0.12 adds a `ProgressReporter` protocol (`start_phase` /
   `update` / `end_phase`), documented in the library's `docs/progress.md`. That's what
   turns the Qt app's indeterminate busy indicator into a real `QProgressBar` — determinate
   for the phases that report a `total` (`legacy_attempt`, `multiplicative_weights`,
   `leximin_outer`), busy for the convergence loops where `total is None`. On a 10-minute
   leximin run over a real pool this is the difference between "working" and "possibly
   hung".
2. **Not being 12 releases behind.** Latest tag is 0.12.10; we're pinned at 0.11.5. The gap
   only gets more expensive to cross.
3. **New capability we don't currently expose** — `load_already_selected` (replacements:
   selecting more people while excluding those already chosen) looks directly useful for
   the app, but is a feature decision, not part of the bump.

## What will break, or might

Not researched properly yet — this list is from skimming the installed package against the
sibling checkout, and needs verifying against the actual 0.12.x changelog.

- **Google Sheets output tab naming.** 0.12 has a `GSheetTabNamer` with `selected_tab_name`
  / `remaining_tab_name` as properties plus `find_unused_tab_suffix()`. The current app
  assigns `data_source.selected_tab_name = "Original Selected - output - "` directly. That
  assignment is likely no longer the right API, and the suffix behaviour (not clobbering
  previous runs' tabs) may now be the library's job rather than ours. **This is the main
  risk in the bump, and it is in exactly the part of the app with no automated coverage.**
- **`RunReport` shape.** New `message_code` / `message_params` fields on report lines exist
  for i18n. Shouldn't affect `as_html()`, but the report-rendering tests will tell us.
- **Deprecations.** `RunReport.add_lines()` already warns; check whether anything the app
  calls is on the way out.
- **Transitive dependency churn** — numpy/cvxpy/mip/highspy versions move, which lands
  straight in the PyInstaller bundle. Re-measure the packaged size and re-run the
  `--self-test` smoke test on all three platforms.

## Rough shape of the work

Ordered so the risky part happens under test, not in a dialog box.

1. **Read the changelog properly** for 0.11.5 → 0.12.10 and replace the guesses above with
   facts. Everything downstream depends on this step being done honestly.
2. **Bump the pin, run the suite unchanged.** By this point the Qt port has unit tests over
   both sessions and e2e tests over the CSV flow. Whatever goes red is the real answer to
   "what does this bump break", and it costs nothing to find out.
3. **Fix the gsheet output API** against the fixture-backed `AbstractDataSource` tests
   first, then verify by hand with the §6.3 checklist from the Qt plan. Pay particular
   attention to running a selection twice against the same sheet — that's where the tab
   suffix logic lives.
4. **Add `QtProgressReporter`.** The Qt worker already carries an unused
   `progress_reporter` argument for this, so it should be one new module plus the
   `QProgressBar` wiring. Red-first: the reporter emits Qt signals, the tests assert phase
   ordering and payloads with `qtbot.waitSignal`.
5. **Throttle it.** The library explicitly does not throttle — it calls `update()` every
   iteration, "hundreds of times per second on a fast solver", and says throttling is the
   caller's responsibility. Emitting a Qt signal per call would flood the event loop. Cap
   at ~10 Hz, but always flush phase transitions immediately so the label never lags.
   Needs a test that hammers `update()` and asserts the emitted-signal count is bounded.
   See https://github.com/sortitionfoundation/opendlp/raw/refs/heads/main/backend/src/opendlp/adapters/sortition_progress.py
   for an example in another project.
6. **Re-measure the bundle** and re-run the packaged smoke test everywhere.

## Related, but separate

- **Cancellation.** Still not possible: the library swallows reporter exceptions by design,
  so Cancel can't be implemented by raising from one, and killing a `QThread` mid-solve
  isn't acceptable. It needs upstream support — `should_cancel()` on the protocol, or a
  cancellation token. Worth raising as an issue on `sortition-algorithms` whether or not we
  take this bump; you own the repo, so it's cheap to ask for.
- **`load_already_selected` / replacements** — a feature for the app, not part of the bump.
  Would want its own UI (a third file input, or a third tab) and its own plan.
