$(function () {


  function init_page() {
    // CSV elements
    const csv_file_features_input = document.getElementById("csv-file-features");
    csv_file_features_input.addEventListener("click", clear_file_value, false);
    csv_file_features_input.addEventListener("change", handle_csv_file_features, false);
    const csv_file_people_input = document.getElementById("csv-file-people");
    csv_file_people_input.addEventListener("click", clear_file_value, false);
    csv_file_people_input.addEventListener("change", handle_csv_file_people, false);
    const csv_run_btn = document.getElementById('csv-run-btn');
    csv_run_btn.addEventListener('click', handle_csv_run_button, false);
    const csv_run_test_btn = document.getElementById('csv-run-test-btn');
    csv_run_test_btn.addEventListener('click', handle_csv_run_test_button, false);
    const csv_panel_size_input = document.getElementById("csv-panel-size");
    csv_panel_size_input.addEventListener("input", handle_csv_panel_size, false);

    // Google Spreadsheet elements
    const g_sheet_name_input = document.getElementById("g-sheet-name");
    g_sheet_name_input.addEventListener("input", handle_g_sheet_name, false);
    const g_sheet_respondents_tab_name_input = document.getElementById("g-sheet-respondents-tab");//for respondents tab
    g_sheet_respondents_tab_name_input.addEventListener("input", handle_respondents_tab_name, false);//for features/categories tab
    const g_sheet_features_tab_name_input = document.getElementById("g-sheet-features-tab");//for features/categories tab
    g_sheet_features_tab_name_input.addEventListener("input", handle_features_tab_name, false);//for features/categories tab
    const g_sheet_gen_rem_tab_input = document.getElementById("g-sheet-gen-rem-tab");//for generate remaining tab checkbox
    g_sheet_gen_rem_tab_input.addEventListener('change', handle_gen_rem_tab, false);// for generate remaining tab checkbox
    const load_g_sheet_btn = document.getElementById('load-g-sheet-btn');
    load_g_sheet_btn.addEventListener('click', handle_load_g_sheet_btn, false);
    const g_sheet_number_selections_input = document.getElementById("g-sheet-number-selections");
    g_sheet_number_selections_input.addEventListener("input", handle_g_sheet_number_selections, false);
    const g_sheet_panel_size_input = document.getElementById("g-sheet-panel-size");
    g_sheet_panel_size_input.addEventListener("input", handle_g_sheet_panel_size, false);
    const g_sheet_run_btn = document.getElementById('g-sheet-run-btn');
    g_sheet_run_btn.addEventListener('click', handle_g_sheet_run_button, false);
    const g_sheet_run_test_btn = document.getElementById('g-sheet-run-test-btn');
    g_sheet_run_test_btn.addEventListener('click', handle_g_sheet_run_test_button, false);
  }

  eel.expose(alert_user);
  function alert_user(message, is_error) {
    const alerts_div = document.getElementById("user-alerts");
    alerts_div.classList.add("alert");
    if (is_error) {
      alerts_div.classList.add("alert-danger");
    } else {
      alerts_div.classList.add("alert-info");
    }
    alerts_div.textContent = message;
  }

  //////////////////////////////////////////
  // functions for CSV files only - calling from JS to Python
  //////////////////////////////////////////

  // this allows repeat upload of a file
  // from: https://stackoverflow.com/a/12102992/3189
  function clear_file_value() {
    this.value = null;
  }

  function handle_csv_file_features() {
    const file_handle = this.files[0];
    const reader = new FileReader();
    reader.onload = csv_file_features_loaded;
    reader.readAsText(file_handle);
  }

  function handle_csv_file_people() {
    const file_handle = this.files[0];
    const reader = new FileReader();
    reader.onload = csv_file_people_loaded;
    reader.readAsText(file_handle);
  }

  function csv_file_features_loaded(e) {
    const file_contents = e.target.result;
    eel.handle_csv_file_features_content(file_contents);
  }

  function csv_file_people_loaded(e) {
    const file_contents = e.target.result;
    eel.handle_csv_file_people_content(file_contents);
  }

  function enable_download(download_link_id, file_contents, filename) {
    let download_link = document.getElementById(download_link_id);
    download_link.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(file_contents));
    download_link.setAttribute('download', filename);
    download_link.classList.remove("disabled");
  }

  eel.expose(enable_csv_selected_download);
  function enable_csv_selected_download(file_contents, filename) {
    console.log("in csv_enable_selected_download");
    enable_download("csv-download-selected-btn", file_contents, filename);
  }

  eel.expose(enable_csv_remaining_download);
  function enable_csv_remaining_download(file_contents, filename) {
    console.log("in csv_enable_remaining_download");
    enable_download("csv-download-remaining-btn", file_contents, filename);
  }

  function handle_csv_panel_size() {
    eel.update_csv_panel_size(this.value);
  }

  function handle_csv_run_button() {
    eel.csv_run_selection();
  }

  function handle_csv_run_test_button() {
    eel.csv_run_test_selection();
  }

  //////////////////////////////////////////
  // functions for CSV files only - calling from Python to JS
  //////////////////////////////////////////

  eel.expose(update_csv_features_output_area);
  function update_csv_features_output_area(output_html) {
    const output_area = document.getElementById("csv-output-area-features-target-p");
    output_area.innerHTML = output_html;
  }

  eel.expose(update_csv_selection_output_area);
  function update_csv_selection_output_area(output_html) {
    const output_area = document.getElementById("csv-output-area-selection-target-p");
    output_area.innerHTML = output_html;
  }

  eel.expose(update_csv_selection_range);
  function update_csv_selection_range(min_selection, max_selection) {
    const selection_label = document.querySelector("label[for=csv-panel-size]");
    selection_label.textContent = "Step 3: Specify the number of people to select (" +
      min_selection + "-" + max_selection + ")";
    const selection_input = document.getElementById("csv-panel-size");
    selection_input.setAttribute("min", min_selection);
    selection_input.setAttribute("max", max_selection);
  }

  eel.expose(enable_csv_selection_content);
  function enable_csv_selection_content() {
    var csv_file_people_input = document.getElementById("csv-file-people");
    csv_file_people_input.disabled = false;
  }

  eel.expose(set_csv_panel_size);
  function set_csv_panel_size(panel_size) {
    var csv_panel_size_input = document.getElementById("csv-panel-size");
    csv_panel_size_input.value = panel_size;
  }

  eel.expose(enable_csv_run_button);
  function enable_csv_run_button() {
    var csv_run_btn = document.getElementById('csv-run-btn');
    var csv_run_test_btn = document.getElementById('csv-run-test-btn');
    csv_run_btn.disabled = false;
    csv_run_test_btn.disabled = false;
  }

  eel.expose(disable_csv_run_button);
  function disable_csv_run_button() {
    var csv_run_btn = document.getElementById('csv-run-btn');
    var csv_run_test_btn = document.getElementById('csv-run-test-btn');
    csv_run_btn.disabled = true;
    csv_run_test_btn.disabled = true;
  }


  /////////////////////////////////////////
  // functions for Google Spreadsheets only - calling from JS to Python
  /////////////////////////////////////////

  function handle_g_sheet_name() {
    eel.update_g_sheet_name(this.value);
  }

  function handle_respondents_tab_name() {
    eel.update_respondents_tab_name(this.value);
  }

  function handle_features_tab_name() {
    eel.update_features_tab_name(this.value);
  }

  function handle_gen_rem_tab() {
    if (this.checked == true) {
      eel.update_gen_rem_tab(this.value);
    } else {
      eel.update_gen_rem_tab("off");
    }
  }

  function handle_load_g_sheet_btn() {
    eel.load_g_sheet();
  }

  eel.expose(enable_load_g_sheet_btn);
  function enable_load_g_sheet_btn() {
    var load_g_sheet_btn = document.getElementById('load-g-sheet-btn');
    load_g_sheet_btn.disabled = false;
  }

  function handle_g_sheet_number_selections() {
    eel.update_number_selections(this.value);
  }

  function handle_g_sheet_panel_size() {
    eel.update_g_sheet_panel_size(this.value);
  }

  function handle_g_sheet_run_button() {
    eel.g_sheet_run_selection();
  }

  function handle_g_sheet_run_test_button() {
    eel.g_sheet_run_test_selection();
  }

  /////////////////////////////////////////
  // functions for Google Spreadsheets only - calling from Python to JS
  /////////////////////////////////////////

  eel.expose(update_g_sheet_features_output_area);
  function update_g_sheet_features_output_area(output_html) {
    const output_area = document.getElementById("g-sheet-output-area-features-target-p");
    output_area.innerHTML = output_html;
  }

  eel.expose(update_g_sheet_selection_range);
  function update_g_sheet_selection_range(min_selection, max_selection) {
    const selection_label = document.querySelector("label[for=g-sheet-panel-size]");
    selection_label.textContent = "Step 3: Specify the number of people to select (" +
      min_selection + "-" + max_selection + ")";
    const selection_input = document.getElementById("g-sheet-panel-size");
    selection_input.setAttribute("min", min_selection);
    selection_input.setAttribute("max", max_selection);
  }

  eel.expose(update_g_sheet_selection_output_area);
  function update_g_sheet_selection_output_area(output_html) {
    const output_area = document.getElementById("g-sheet-output-area-selection-target-p");
    output_area.innerHTML = output_html;
  }

  eel.expose(enable_g_sheet_selection_content);
  function enable_g_sheet_selection_content() {
    g_sheet_file_people_input.disabled = false;
  }

  eel.expose(set_g_sheet_panel_size);
  function set_g_sheet_panel_size(panel_size) {
    var g_sheet_panel_size_input = document.getElementById("g-sheet-panel-size");
    g_sheet_panel_size_input.value = panel_size;
  }

  eel.expose(enable_g_sheet_run_button);
  function enable_g_sheet_run_button() {
    var g_sheet_run_btn = document.getElementById('g-sheet-run-btn');
    var g_sheet_run_test_btn = document.getElementById('g-sheet-run-test-btn');
    g_sheet_run_btn.disabled = false;
    g_sheet_run_test_btn.disabled = false;
  }

  eel.expose(disable_g_sheet_run_button);
  function disable_g_sheet_run_button() {
    var g_sheet_run_btn = document.getElementById('g-sheet-run-btn');
    var g_sheet_run_test_btn = document.getElementById('g-sheet-run-test-btn');
    g_sheet_run_btn.disabled = true;
    g_sheet_run_test_btn.disabled = true;
  }

  ////////////////////////////////////////
  //Some functions for the output area - shared by CSV and GSheets
  ////////////////////////////////////////

  eel.expose(update_detailed_log_messages_area);
  function update_detailed_log_messages_area(output_html) {
    const output_area = document.getElementById("output-area-detailed-log-target-p");
    output_area.innerHTML = output_html;
  }

  init_page();
}());
