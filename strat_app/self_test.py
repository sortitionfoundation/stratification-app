# ABOUTME: The --self-test check: build the window, run a small selection, report and exit.
# ABOUTME: Run against a packaged build, it catches the packaging faults that reach users first.

from PySide6.QtCore import QEventLoop, QTimer

from strat_app.qt.main_window import MainWindow

TIMEOUT_MS = 120_000
PANEL_SIZE = 4

# A tiny problem, chosen so the answer is obvious: two categories wanting two or three
# people each, and a pool of ten to pick four from.
CATEGORIES = "category,name,min,max\ngender,Female,2,3\ngender,Male,2,3\n"
PEOPLE_COLUMNS = (
    "nationbuilder_id,first_name,last_name,mobile_number,email,primary_address1,"
    "primary_address2,primary_city,zip_royal_mail,tag_list,age,gender"
)
POOL_SIZE = 10


def people_csv() -> str:
    rows = [PEOPLE_COLUMNS]
    for index in range(POOL_SIZE):
        gender = "Female" if index % 2 else "Male"
        rows.append(
            f"id-{index},First{index},Last{index},0770090000{index},person{index}@example.org,"
            f"{index} Test Street,,Testville,TE{index} 1ZZ,,{30 + index},{gender}"
        )
    return "\n".join(rows) + "\n"


def run_self_test(window: MainWindow) -> int:
    """
    Put the app through its paces without a user, and return an exit code.

    Building the window catches a missing Qt platform plugin. Running a selection
    catches the scientific stack failing to import - which a packaged build manages to
    do in ways a development one never does.
    """
    tab = window.csv_tab
    tab.session.add_feature_content(CATEGORIES)
    if tab.session.features is None:
        print("self test: the categories did not load")
        return 1
    tab.session.add_people_content(people_csv())
    if tab.session.people is None:
        print("self test: the people did not load")
        return 1

    tab.session.set_panel_size(PANEL_SIZE)
    _run_and_wait(window)

    if not tab.save_selected_button.isEnabled():
        print("self test: the selection produced no output")
        return 1
    print(f"self test: ok - selected {PANEL_SIZE} of {POOL_SIZE}")
    return 0


def _run_and_wait(window: MainWindow) -> None:
    """Run a selection and spin the event loop until the worker is done, or time is up."""
    loop = QEventLoop()
    window.task_runner.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(TIMEOUT_MS)
    window.csv_tab.run_selection()
    loop.exec()
