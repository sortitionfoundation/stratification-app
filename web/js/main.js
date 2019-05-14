$(function(){

    function init_page() {
        const categories_file_input = document.getElementById("categories-file");
        categories_file_input.addEventListener("change", handle_categories_file, false);
        const selection_file_input = document.getElementById("selection-file");
        selection_file_input.addEventListener("change", handle_selection_file, false);
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

    eel.expose(update_selection_output_area);
    function update_selection_output_area(output_text) {
        const output_area = document.getElementById("output-area-selection-target-p");
        output_area.textContent = output_text;
    }

    function handle_run_button() {
        eel.run_selection();
    }

    eel.expose(enable_run_button);
    function enable_run_button() {
        const run_button = document.getElementById("run-btn");
        run_button.disabled = false;
    }

    eel.expose(enable_download);
    function enable_download(file_contents, filename) {
        console.log("in enable_download");
        console.log(file_contents);
        let download_link = document.getElementById("download-btn");
        download_link.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(file_contents));
        download_link.setAttribute('download', filename);
        download_link.classList.remove("disabled");
    }

    init_page();
}());
