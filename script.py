from io import StringIO

import eel


@eel.expose
def handle_category_contents(file_contents):
    the_file = StringIO(file_contents)
    line_count = len(the_file.readlines())
    eel.update_categories_output_area(line_count)


@eel.expose
def handle_selection_contents(file_contents):
    the_file = StringIO(file_contents)
    line_count = len(the_file.readlines())
    eel.update_selection_output_area(line_count)


@eel.expose
def trigger_download():
    file_contents = 'hello\nworld\n'
    eel.cause_download(file_contents, 'file.txt')


def main():
    eel.init('web')  # Give folder containing web files
    eel.start('main.html', size=(500, 500))    # Start


if __name__ == '__main__':
    main()
