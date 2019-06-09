$(function(){

    function init_page() {
        const categories_file_input = document.getElementById("categories-file");
        categories_file_input.addEventListener("change", handle_categories_file, false);
        const selection_file_input = document.getElementById("selection-file");
        selection_file_input.addEventListener("change", handle_selection_file, false);
        const select_number_people_input = document.getElementById("selection-number");
        select_number_people_input.addEventListener("input", handle_number_people, false);
        const run_btn = document.getElementById('run-btn');
        run_btn.addEventListener('click', handle_run_button, false);
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

    function categories_file_loaded(e) {
        const file_contents = e.target.result;
        eel.handle_category_contents(file_contents);
    }

    function selection_file_loaded(e) {
        const file_contents = e.target.result;
        eel.handle_selection_contents(file_contents);
    }

    eel.expose(update_categories_output_area);
    function update_categories_output_area(output_text) {
        const output_area = document.getElementById("output-area-categories-target-p");
        output_area.textContent = output_text;
    }

    eel.expose(update_selection_range);
    function update_selection_range(min_selection, max_selection) {
        const selection_label = document.querySelector("label[for=selection-number]");
        selection_label.textContent = "Number of people to select (" +
             min_selection + "-" + max_selection + ")";
        const selection_input = document.getElementById("selection-number");
        selection_input.setAttribute("min", min_selection);
        selection_input.setAttribute("max", max_selection);
    }

    eel.expose(update_selection_output_area);
    function update_selection_output_area(output_text) {
        const output_area = document.getElementById("output-area-selection-target-p");
        output_area.textContent = output_text;
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
