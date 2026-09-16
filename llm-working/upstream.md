# Upstream issues for `sortition-algorithms`

Found while researching the 0.11.5 → 0.12.10 bump for this app
(`llm-working/library-bump.md`). All line numbers are against tag **0.12.10**.

Written as issue drafts — title, then body — so they can be pasted straight into
<https://github.com/sortitionfoundation/sortition-algorithms/issues>. Ordered by how much
they matter to a caller.

---

## 1. `ConfigurationError` escapes `run_stratification` where `ValueError` used to be caught

**Labels:** bug, regression

### What happens

`run_stratification` catches four exception types around its call to `find_random_sample`
(`core.py:574`):

```python
except (errors.SelectionError, ValueError, RuntimeError, errors.InfeasibleQuotasCantRelaxError) as error:
    report.add_error(error)
    return False, people_selected, report
```

In 0.11.5, `find_random_sample` raised plain `ValueError` for its four
invalid-argument cases, so they were caught here and turned into a
`(False, [], report)` result with the error in the report.

In 0.12 those four sites were changed to raise the new `ConfigurationError`
(`core.py:299`, `:306`, `:312`, `:381`). But `ConfigurationError` subclasses
`SortitionBaseError`, which subclasses `Exception` — **not `ValueError`**
(`errors.py:13`, `:38`). So the except clause no longer catches them and they propagate out
of `run_stratification`.

### Why it matters

A caller that was correctly handling the documented `(success, committees, report)` contract
now gets an exception instead. The four affected cases are:

- `test_selection=True` with `number_selections > 1`
- `selection_algorithm="legacy"` with `number_selections > 1`
- `selection_algorithm="diversimax"` with `number_selections > 1`
- an unknown `selection_algorithm`

The first of those is reachable from a UI where the user can set both independently — it is
how we found this. The user goes from a tidy report explaining the problem to a generic
"unexpected error" with a traceback behind it.

The docstring is also now inaccurate: `core.py:526` still says
`ValueError: For invalid parameters`.

### Suggested fix

Add `errors.ConfigurationError` to the except tuple (or, more robustly, catch
`errors.SortitionBaseError`, which covers `SelectionError`, `ConfigurationError`,
`BadDataError` and `InfeasibleQuotasCantRelaxError` in one), and update the docstring's
`Raises:` section.

A regression test along the lines of "every documented invalid-argument case returns
`success=False` rather than raising" would stop this recurring the next time an exception
type is introduced.

---

## 2. `ProgressReporter` has no way to request cancellation

**Labels:** enhancement

### The problem

`ProgressReporter` gives a caller a live view of a long-running selection, which is exactly
what a desktop or web UI needs. But there is no way to ask that selection to stop.

The obvious hack — raise from `update()` — is deliberately defeated: `coerce_reporter` wraps
every caller-supplied reporter in `ErrorSwallowingReporter`, which catches and logs
everything (`progress.py`). That is the right default for a buggy reporter, and
`docs/progress.md` documents it as intentional. But it means cancellation has no seam at
all.

The alternatives available to a caller are all bad:

- kill the worker thread — not safe, and not possible to do cleanly in Qt
- run the selection in a subprocess purely so it can be killed — a lot of machinery, and it
  breaks the in-process reporter
- wait it out — a leximin run over a real pool can be 10+ minutes

### What would help

Either:

1. **`should_cancel() -> bool` on the protocol**, called at the same points `update()` is
   called. The library checks it and raises a `SelectionCancelledError` (or returns
   `success=False` with a "cancelled" report line). Default implementation returns `False`,
   so it is backwards compatible and `NullProgressReporter` needs one extra method.
2. **A separate cancellation token argument** to `run_stratification` /
   `find_random_sample` — an object with an `is_set()`-shaped API, so
   `threading.Event` works directly.

(1) keeps everything on one object the caller already supplies. (2) separates "observing"
from "controlling", which is arguably cleaner and lets a caller cancel without also wanting
progress.

Either way, the important part is that the check happens **inside the convergence loops**,
not just between phases — a maximin or leximin inner loop is where the time goes.

Cancelling should leave the caller with a clear signal that the run was cancelled rather
than that it failed, so a UI can say "cancelled" instead of "something went wrong".

---

## 3. `GSheetDataSource.selected_tab_name` / `remaining_tab_name` look like inputs but are outputs

**Labels:** documentation, api

### What they look like

`GSheetDataSource.__init__` sets:

```python
self.selected_tab_name = ""
self.remaining_tab_name = ""
```

(`adapters.py:553-554`). Sitting next to `feature_tab_name`, `people_tab_name` and
`already_selected_tab_name` — which _are_ inputs, and _are_ constructor arguments — these
read unmistakably as "set these to choose your output tab names".

### What they actually are

They are write-only-by-the-library result attributes. `write_selected` and `write_remaining`
take the names from `self.tab_namer` and then _assign_ these fields with whatever the created
tab ended up being called:

```python
tab_selected = self._create_tab(self.tab_namer.selected_tab_name())
...
self.selected_tab_name = tab_selected.title      # adapters.py:843
```

Nothing ever reads them. A caller who sets them gets no error, no warning, and no effect —
their value is silently overwritten the moment a selection is written.

### How we know it bites

The Sortition Foundation desktop app did exactly this for years:

```python
self.data_source.selected_tab_name = self.original_selected_tab_name
self.data_source.remaining_tab_name = self.remaining_tab_name
```

immediately before `output_selected_remaining`. It had no effect (the values it set happened
to equal the library's own defaults, so nobody noticed). The lines were dropped in a
refactor, and when we later went looking for how to make the tab names configurable we
assumed the drop was the bug — it wasn't, but it cost real time to establish that.

### Suggested fix

Any of, in rough order of preference:

1. Rename to `last_written_selected_tab_name` / `last_written_remaining_tab_name`, which
   says what they are.
2. Make them read-only properties backed by private attributes, so assignment fails loudly.
3. At minimum, a docstring or comment on both saying "output only — set by
   `write_selected()` / `write_remaining()`; to control the names, use `tab_namer`".

---

## 4. `GSheetTabNamer` stubs are hard to use from a UI: the suffix has no separator

**Labels:** enhancement, api

`find_unused_tab_suffix` builds candidate names by direct concatenation
(`adapters.py:475-476`):

```python
selected_tab_name_candidate = f"{self.selected_tab_name_stub}{number}"
```

That works because the built-in stubs end in `" - "`, giving
`Original Selected - output - 0`. But any caller that exposes the stub to a user gets
`Panel A0` when the user types `Panel A`, which looks like a bug to them. The stub is the
natural place for a UI to hang a "what should the output tabs be called?" field, and this
makes that harder than it needs to be.

Options that would help:

- a `separator` attribute on `GSheetTabNamer`, defaulting to `""` so nothing changes for
  existing callers, and settable to `" - "` alongside a stub that has no trailing space;
- or a method that returns the name a given stub _would_ produce, so a UI can show a preview
  without reimplementing the format string;
- or, at minimum, a note in the class docstring that the stub is concatenated directly and
  should normally end in a separator.

Related: `find_unused_tab_suffix` gives up silently after 1000 attempts, leaving
`_write_tab_suffix` empty, and the next call to `selected_tab_name()` then raises a
`SelectionError` about a "logic error". A spreadsheet with 1000 old output tabs is
implausible, but the failure mode reads as an internal bug rather than "you have too many
output tabs, delete some" — worth a clearer message if it's cheap.

---

## 5. `load_features` does not strip its header names, but `load_people` does

**Labels:** bug

### What happens

0.12 fixed the "stray space in a spreadsheet header" problem by normalising header names,
via the new `normalise_iter`. It went into two of the three loaders on `SelectionData`
(`adapters.py`):

```python
def load_features(self, number_to_select: int = 0):
    ...
    headers = list(headers_iter)             # <- not normalised

def load_people(self, settings, features):
    ...
    headers = normalise_iter(headers_iter)   # <- normalised

def load_already_selected(self, settings):
    ...
    headers = normalise_iter(headers_iter)   # <- normalised
```

So a respondents tab with `"  nationbuilder_id  "` in its header row now loads, and a
categories tab with `"  category  "` still fails.

### Why it matters

The failure is the confusing one the fix was meant to eliminate. With a categories tab whose
header cells have leading or trailing spaces:

```
ConfigurationError: Did not find required column name 'category' in the input
Did not find required column name 'name' in the input
Did not find required column name 'min' in the input
Did not find required column name 'max' in the input
```

The user is looking at a spreadsheet with `category`, `name`, `min` and `max` in the header
row, spelled exactly as the error says they should be. There is nothing on screen to
suggest the problem is whitespace.

It is also now inconsistent in a way that is hard to explain: pad the respondents tab and
it works, pad the categories tab and it doesn't.

### Reproduction

```python
from sortition_algorithms import adapters

cats = "  category  ,  name  ,  min  ,  max  \ngender,Female,1,2\n"
adapters.SelectionData(adapters.CSVStringDataSource(cats, "")).load_features()
# ConfigurationError: Did not find required column name 'category' in the input
```

### Suggested fix

`headers = normalise_iter(headers_iter)` in `load_features`, matching its two siblings.
Worth a test over all three loaders together so the next one added doesn't miss it.

---

## 6. Nit: the default settings comment contradicts `DEFAULT_BACKEND`

**Labels:** documentation, good first issue

`settings.py:56`, inside `DEFAULT_SETTINGS`:

```
# solver_backend can be "highspy" "mip" (default), "mip-cbc", "mip-highs", "mip-gurobi"
```

`DEFAULT_BACKEND = "highspy"`, so `(default)` is on the wrong value. There is also a missing
comma between `"highspy"` and `"mip"`.

This text is written into every new user's settings file, so it is the first thing anyone
reads about the setting.

Suggested:

```
# solver_backend can be "highspy" (default), "mip", "mip-cbc", "mip-highs", "mip-gurobi"
```
