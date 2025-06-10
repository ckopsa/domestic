# Collection+JSON Feature Suggestions

Here are three feature ideas to better support Collection+JSON in this repository:

## 1. Hypermedia Controls for Template Data (Enhanced Input Types & Suggestions)

*   **What it is:** This feature would improve how users interact with data input forms (templates). Instead of all fields being plain text boxes, they would render as more appropriate types like checkboxes for true/false values, number inputs, or even dropdown lists for predefined choices.
*   **How it helps:** It makes forms easier and more intuitive to fill out, reduces input errors, and provides a richer user experience. For example, if a field expects a specific set of options, a dropdown would guide the user.
*   **Proposed Implementation:**
    *   Enhance the `TemplateData` model in `src/cj_models.py` to support specifying input types (e.g., `boolean`, `number`) and a list of `options` for dropdowns. Consider adding `pattern`, `min`/`max` for validation.
    *   Update the `TransitionManager` in `src/transitions.py` to try and map data types from your API's OpenAPI schema (like `boolean` or `enum`) to these new fields in `TemplateData`.
    *   Modify the `src/templates/cj_template.html` file to render different HTML input elements (`<input type="checkbox">`, `<input type="number">`, `<select>`) based on these new properties in `TemplateData`.

## 2. Client-Side Enhancement: AJAX Form Submission for Templates

*   **What it is:** When you submit a form to create a new item (using the "Template" section), instead of the whole page reloading, the data would be sent in the background using JavaScript (AJAX).
*   **How it helps:** This makes creating new items feel much faster and smoother, as the page doesn't have to refresh completely. The new item could even be dynamically added to the list on the current page.
*   **Proposed Implementation:**
    *   Add JavaScript code to `src/templates/cj_template.html` or a linked JS file.
    *   This script would intercept the template form submission, prevent default browser action, serialize form data, send the data using an AJAX `POST` (or the method specified in `template.method`) request to `template.href`.
    *   Handle the AJAX response by displaying a success/error message, or by dynamically updating the current page (e.g., adding the new item to the list).

## 3. Support for Collection+JSON Read-Only and Write-Only Semantics

*   **What it is:** The Collection+JSON standard allows data fields to be marked as "read-only" (can be seen but not changed by the client) or "write-only" (can be sent by the client but might not be shown back). This feature would add support for these concepts.
*   **How it helps:** It makes your API clearer about what data can be modified or submitted. For example, an "ID" field might be read-only, or a password field might be write-only. This aligns the implementation more closely with the Collection+JSON specification.
*   **Proposed Implementation:**
    *   Add `read_only: Optional[bool] = None` and `write_only: Optional[bool] = None` to the `ItemData` and `TemplateData` models in `src/cj_models.py`.
    *   Update the `TransitionManager` in `src/transitions.py` to set these flags based on your API's OpenAPI schema (e.g., if a property is marked `readOnly: true` in the schema).
    *   Modify `src/cj_models.py` (specifically the `to_cj_data` method and how templates are built by `CollectionJsonRepresentor`) to ensure:
        *   Write-only fields are excluded when generating `Item.data` for display.
        *   Read-only fields in `Template.data` are excluded from submission or are shown as non-editable if they have default values.
    *   Update `src/templates/cj_template.html` to:
        *   Not display `data_point` in item listings if `data_point.write_only` is true.
        *   Render input fields as `disabled` or as static text if `data_item.read_only` is true in templates.
