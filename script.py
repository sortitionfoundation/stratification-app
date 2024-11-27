import platform
import sys
from io import StringIO

import eel
import gspread

from stratification import (
	PeopleAndCatsCSV,
	PeopleAndCatsGoogleSheet,
	NoSettingsFile,
	Settings,
)

# to be honest this is no longer a file contents class - it's a GUI interface handler
# all the "content" has been moved into the PeopleAndCats class and its children
class FileContents():

	def __init__(self):
		self.PeopleAndCats = None
		self._settings = None
		# All of these below are only used in the Google Sheet version
		self.g_sheet_name = ''
		self.respondents_tab_name = 'Respondents' # Instance attribute for Advanced Settings
		self.category_tab_name = 'Categories' # Instance attribute for Advanced Settings
		self.gen_rem_tab = 'on' # Instance attribute for Advanced Settings
		self.number_selections = 1 # Instance attribute for Advanced Settings (then later stored in PeopleAndCats)

	@property
	def settings(self):
		self._init_settings()
		return self._settings

	def _init_settings(self):
		"""
		Call from lots of places to report the error early
		"""
		message = ""
		if self._settings is None:
			self._settings, message = Settings.load_from_file()
		return message	

	def _add_category_content(self, input_content):
		min_selection = 0
		max_selection = 0
		msg = []
		try:
			message = self._init_settings()
			if message != "":
				msg += [ message ]
		except Exception as error:
			self.PeopleAndCats.category_content_loaded = False
			msg += [ "Error reading in settings file: {}".format(error) ]
		try:
			msg2, min_selection, max_selection = self.PeopleAndCats.load_cats( input_content, self.category_tab_name, self._settings )
			msg += msg2
		except gspread.exceptions.APIError as e:
			msg3 = [ "API error causing delay. Please wait a couple of seconds while gsheet updates. After waiting you may need to reload sheet. For the record, the API error is {} ".format(e) ]
			msg += msg3
		except Exception as error:
			self.PeopleAndCats.category_content_loaded = False
			msg += [ "Error reading in categories file: {}".format(error) ]
			print(msg)
		eel.update_categories_output_area("<br />".join(msg))
		self.update_selection_content()
		eel.update_selection_range(min_selection, max_selection)
		# if these are the same just set the value!
		if min_selection == max_selection and min_selection > 0:
			eel.set_select_number_people(str(min_selection))
			self.PeopleAndCats.number_people_to_select = int(min_selection)
		# if we've already uploaded people, we need to re-process them with the
		# (possibly) new categories settings
		if self.PeopleAndCats.people_content_loaded:
			dummy_file_contents=''
			msg = self.PeopleAndCats.load_people(self.settings, dummy_file_contents, self.respondents_tab_name, self.category_tab_name, self.gen_rem_tab)
			eel.update_selection_output_area("<br />".join(msg))
		self.update_run_button()

	# called from CSV input
	def add_category_content(self, file_contents):
		if file_contents != '':
			self.PeopleAndCats = PeopleAndCatsCSV()
			self._add_category_content( file_contents )
			
	def _clear_messages(self, normal_message = "Number of categories: You must (re)load sheet..." ):
		eel.update_categories_output_area( normal_message )
		eel.update_selection_output_area( normal_message )
		eel.update_selection_output_messages_area("")
		eel.set_select_number_people('')

	# called from g-sheet input
	def update_g_sheet_name(self, g_sheet_name_input):
		self._clear_messages() 
		self.g_sheet_name = g_sheet_name_input
		if self.g_sheet_name != '':
			eel.enable_load_g_sheet_btn()

    # user has hit the (re)load button 
	# do cats and people at same time...	
	def load_g_sheet(self):
		# this can happen if they enter something and then delete it...
		if self.g_sheet_name == '':
			self._clear_messages( "Please enter a spreadsheet name..." )
		else:
			self._clear_messages( "Requesting data from sheet..." )
			try:
				self.PeopleAndCats = PeopleAndCatsGoogleSheet()
				# tell this object what this currently is...
				self.PeopleAndCats.number_selections = self.number_selections
				msg = []
				if self.number_selections > 1:
					msg += ["<b>WARNING</b>: You've asked for {} selections. You cannot use the <i>Produce a Test Panel</i> button if you want more than 1 selection and no Remaining tab will be created.".format(self.number_selections)]
				self._add_category_content( self.g_sheet_name )
				dummy_file_contents=''
				msg += self.PeopleAndCats.load_people(self.settings, dummy_file_contents, self.respondents_tab_name, self.category_tab_name, self.gen_rem_tab )
				eel.update_selection_output_area("<br />".join(msg))
				self.update_run_button()
				eel.enable_load_g_sheet_btn()
			except Exception as error:
				eel.update_categories_output_area( "Please wait a couple of seconds while gsheet updates. After waiting you may need to reload sheet. Current error is: {}".format(error))
	###############################################################################		
	###The next functions read in extra instance variables for advanced settings###	
	###############################################################################
	def update_respondents_tab_name(self, respondents_tab_name_input):
		self._clear_messages()
		self.respondents_tab_name = respondents_tab_name_input

	def update_categories_tab_name(self, categories_tab_name_input):
		self._clear_messages()
		self.category_tab_name = categories_tab_name_input

	def update_gen_rem_tab(self, gen_rem_tab_input):
		self.gen_rem_tab = gen_rem_tab_input
		# never generate a remaining tab if doing a multiple selection
		if self.number_selections > 1:
			self.gen_rem_tab = 'off'

	def update_number_selections(self, number_selections_input):
		self._clear_messages()
		if number_selections_input == '':
			self.number_selections = 1
		else:
			self.number_selections = int(number_selections_input)
		# never generate a remaining tab if doing a multiple selection
		if self.number_selections > 1:
			self.gen_rem_tab = 'off'
		else: # but turn it on if = 1 (this could be wrong if the person wants it off!) if this has changed back to 1...
			self.gen_rem_tab = 'on'
	########################################
	###End of Advanced Settings variables###
	########################################
	### From here 'selection' means people...
	def add_selection_content(self, file_contents):
		self._init_settings()
		# this calls update internally
		msg = self.PeopleAndCats.load_people(self.settings, file_contents, self.respondents_tab_name, self.category_tab_name, self.gen_rem_tab)
		eel.update_selection_output_area("<br />".join(msg))
		self.update_run_button()

	# 'selection' means people...
	def update_selection_content(self):
		if self.PeopleAndCats.category_content_loaded:
			eel.enable_selection_content()

	def update_run_button(self):
		if self.PeopleAndCats.category_content_loaded and self.PeopleAndCats.people_content_loaded and self.PeopleAndCats.number_people_to_select > 0:
			eel.enable_run_button()
		else:
			eel.disable_run_button()
		if self.PeopleAndCats.number_people_to_select <= 0:
			eel.set_select_number_people('')

	def update_number_people(self, number_people):
		if number_people == '':
			self.PeopleAndCats.number_people_to_select = 0
		else:
			self.PeopleAndCats.number_people_to_select = int(number_people)
		self.update_run_button()

	def run_selection(self, test_selection ):
		self._init_settings()
		# they may have hit this button again, so clear the output area so it's more obvious
		eel.update_selection_output_messages_area("Selecting... please wait...<br />")
		success, output_lines = self.PeopleAndCats.people_cats_run_stratification( self.settings, test_selection )		
		if success and self.PeopleAndCats.get_selected_file() is not None and self.PeopleAndCats.get_remaining_file() is not None:
			eel.enable_selected_download(self.PeopleAndCats.get_selected_file().getvalue(), 'selected.csv')
			eel.enable_remaining_download(self.PeopleAndCats.get_remaining_file().getvalue(), 'remaining.csv')
		# print output_lines to the App:
		eel.update_selection_output_messages_area("<br />".join(output_lines))


# global to hold contents uploaded from JS
# not really - now just a GUI event handler more or less...
csv_files = FileContents()

@eel.expose
def handle_category_contents(file_contents):
	csv_files.add_category_content(file_contents)

# 'selection' means people...
@eel.expose
def handle_selection_contents(file_contents):
	csv_files.add_selection_content(file_contents)

@eel.expose
def update_g_sheet_name(g_sheet_name):
	csv_files.update_g_sheet_name(g_sheet_name)

@eel.expose
def load_g_sheet():
	csv_files.load_g_sheet()

#############################
###Start Advanced Settings###
#############################
@eel.expose
def update_respondents_tab_name(respondents_tab_name):
	csv_files.update_respondents_tab_name(respondents_tab_name)

@eel.expose
def reload_respondents_tab():
	csv_files.update_respondents_tab_name('')

@eel.expose
def update_categories_tab_name(categories_tab_name):
	csv_files.update_categories_tab_name(categories_tab_name)

@eel.expose
def reload_categories_tab():
	csv_files.update_categories_tab_name('')

@eel.expose
def update_gen_rem_tab(gen_rem_tab):
	csv_files.update_gen_rem_tab(gen_rem_tab)
	
@eel.expose
def reload_gen_rem_tab():
	csv_files.update_gen_rem_tab('')

@eel.expose
def update_number_selections(number_selections):
	csv_files.update_number_selections(number_selections)

@eel.expose
def reload_number_selections():
	csv_files.update_number_selections('')

###########################
###End Advanced Settings###
###########################

@eel.expose
def update_number_people(number_people):
	csv_files.update_number_people(number_people)

@eel.expose
def run_selection():
	csv_files.run_selection( False )

@eel.expose
def run_test_selection():
	csv_files.run_selection( True )

def main():
	default_size = (800, 800)
	eel.init('web')  # Give folder containing web files
	try:
		eel.start('main.html', size=default_size)
	except EnvironmentError:
		# on Windows 10 try Edge if Chrome not available
		if sys.platform in ('win32', 'win64') and int(platform.release()) >= 10:
			eel.start('main.html', mode='edge', size=default_size)
		else:
			raise


if __name__ == '__main__':
	main()
