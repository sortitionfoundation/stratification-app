$(function(){

    function init_page() {
        const categories_file_input = document.getElementById("categories-file");
        categories_file_input.addEventListener("click", clear_file_value, false);
        categories_file_input.addEventListener("change", handle_categories_file, false);
        const categories_g_sheet_name_input = document.getElementById("categories-g-sheet");
        categories_g_sheet_name_input.addEventListener("input", handle_g_sheet_name, false);
        const selection_file_input = document.getElementById("selection-file");
        selection_file_input.addEventListener("click", clear_file_value, false);
        selection_file_input.addEventListener("change", handle_selection_file, false);
        const select_number_people_input = document.getElementById("selection-number");
        select_number_people_input.addEventListener("input", handle_number_people, false);
        const run_btn = document.getElementById('run-btn');
        run_btn.addEventListener('click', handle_run_button, false);
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

    // this allows repeat upload of a file
    // from: https://stackoverflow.com/a/12102992/3189
    function clear_file_value() {
        this.value = null;
    }

    function handle_categories_file() {
        const file_handle = this.files[0];
        const reader = new FileReader();
        reader.onload = categories_file_loaded;
        reader.readAsText(file_handle);
    }

    function handle_selection_file() {
        const file_handle = this.files[0];
        const reader = new FileReader();
        reader.onload = selection_file_loaded;
        reader.readAsText(file_handle);
    }

    function handle_g_sheet_name() {
    	eel.update_g_sheet_name(this.value);
    }

    function categories_file_loaded(e) {
        const file_contents = e.target.result;
        eel.handle_category_contents(file_contents);
    }

    function selection_file_loaded(e) {
        const file_contents = e.target.result;
        eel.handle_selection_contents(file_contents);
    }

    eel.expose(update_categories_output_area);
    function update_categories_output_area(output_html) {
        const output_area = document.getElementById("output-area-categories-target-p");
        output_area.innerHTML = output_html;
    }

    eel.expose(update_selection_range);
    function update_selection_range(min_selection, max_selection) {
        const selection_label = document.querySelector("label[for=selection-number]");
        selection_label.textContent = "Step 3: Specify the number of people to select (" +
             min_selection + "-" + max_selection + ")";
        const selection_input = document.getElementById("selection-number");
        selection_input.setAttribute("min", min_selection);
        selection_input.setAttribute("max", max_selection);
    }

    eel.expose(update_selection_output_area);
    function update_selection_output_area(output_html) {
        const output_area = document.getElementById("output-area-selection-target-p");
        output_area.innerHTML = output_html;
    }
    
    function handle_number_people() {
        eel.update_number_people(this.value);
    }

    eel.expose(update_selection_output_messages_area);
    function update_selection_output_messages_area(output_html) {
        const output_area = document.getElementById("output-area-selection-messages-target-p");
        output_area.innerHTML = output_html;
    }

    function handle_run_button() {
        eel.run_selection();
    }

	eel.expose(enable_selection_content);
    function enable_selection_content() {
        const selection_content = document.getElementById("selection-file");
        selection_content.disabled = false;
    }
	
    eel.expose(enable_run_button);
    function enable_run_button() {
        const run_button = document.getElementById("run-btn");
        run_button.disabled = false;
    }

    function enable_download(download_link_id, file_contents, filename) {
        let download_link = document.getElementById(download_link_id);
        download_link.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(file_contents));
        download_link.setAttribute('download', filename);
        download_link.classList.remove("disabled");
    }

    eel.expose(enable_selected_download);
    function enable_selected_download(file_contents, filename) {
        console.log("in enable_selected_download");
        enable_download("download-selected-btn", file_contents, filename);
    }

    eel.expose(enable_remaining_download);
    function enable_remaining_download(file_contents, filename) {
        console.log("in enable_remaining_download");
        enable_download("download-remaining-btn", file_contents, filename);
    }

    init_page();
}());
