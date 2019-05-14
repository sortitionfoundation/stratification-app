from io import StringIO

import eel


class FileContents():

    def __init__(self):
        self.category_raw_content = ''
        self.selection_raw_content = ''

    def add_category_content(self, file_contents):
        csv_files.category_raw_content = file_contents
        the_file = StringIO(file_contents)
        line_count = len(the_file.readlines())
        eel.update_categories_output_area(line_count)
        self.update_run_button()

    def add_selection_content(self, file_contents):
        csv_files.selection_raw_content = file_contents
        the_file = StringIO(file_contents)
        line_count = len(the_file.readlines())
        eel.update_selection_output_area(line_count)
        self.update_run_button()

    def update_run_button(self):
        if self.category_raw_content and self.selection_raw_content:
            eel.enable_run_button()

    def run_selection(self):
        file_contents = self.category_raw_content + self.selection_raw_content
        eel.enable_download(file_contents, 'file.txt')


# global to hold contents uploaded from JS
csv_files = FileContents()


@eel.expose
def handle_category_contents(file_contents):
    csv_files.add_category_content(file_contents)


@eel.expose
def handle_selection_contents(file_contents):
    csv_files.add_selection_content(file_contents)


@eel.expose
def run_selection():
    csv_files.run_selection()


def main():
    eel.init('web')  # Give folder containing web files
    eel.start('main.html', size=(500, 500))    # Start


if __name__ == '__main__':
    main()
