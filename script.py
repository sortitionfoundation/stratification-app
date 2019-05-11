from io import StringIO

import eel

eel.init('web')                     # Give folder containing web files


@eel.expose
def handle_file_contents(file_contents):
    the_file = StringIO(file_contents)
    line_count = len(the_file.readlines())
    eel.update_output_area(line_count)


eel.start('main.html', size=(500, 200))    # Start
