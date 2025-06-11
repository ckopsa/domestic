# Collection+JSON Feature Ideas

Here are 5 feature ideas to enhance Collection+JSON support in this project:

## 1. Read-Only and Disabled States for Form Fields

*   **Description**: Currently, form fields in templates and queries are always editable. Add support for marking fields as read-only or disabled based on backend logic or schema definitions. This would be useful for displaying data that shouldn't be modified by the user in a form context or for guiding users through a workflow where some fields become active/inactive based on previous selections.
*   **Potential Benefits**: Improved user guidance, better representation of data states, and more sophisticated form-based workflows.
*   **Affected Components**: `cj_models.py` (new attributes in `TemplateData`/`QueryData`), `transitions.py` (OpenAPI schema parsing), `cj_template.html` (HTML rendering logic).

## 2. Support for Collection+JSON "error" Object

*   **Description**: The Collection+JSON specification defines an "error" object for communicating issues to the client. While the models exist (`Error` in `cj_models.py`), this feature is not fully implemented. This involves populating the `error` object during exceptions and rendering these errors clearly in the HTML interface.
*   **Potential Benefits**: Standardized error reporting, improved debugging for API consumers, and a better user experience when errors occur.
*   **Affected Components**: `cj_models.py` (`CollectionJsonRepresentor`), global exception handling middleware, `cj_template.html` (error display).

## 3. Dynamic Client-Side Interactions for `render: "link"` or `render: "embed"`

*   **Description**: The Collection+JSON `link` object can have a `render` property (e.g., "link" for navigation, "embed" for inline display). Currently, all links are treated as simple navigational anchors. This feature would involve adding client-side JavaScript to interpret the `render` property, for example, using AJAX to embed content for `render: "embed"` links.
*   **Potential Benefits**: Richer, more dynamic user interfaces without full page reloads, closer adherence to Collection+JSON capabilities.
*   **Affected Components**: `cj_template.html` (JavaScript for dynamic rendering), `cj_models.py` (ensure `Link` model captures `render`).

## 4. Enhanced Support for Link Headers and Conditional Requests

*   **Description**: Improve support for HTTP mechanisms like `Link` headers (for pagination, related resources not directly part of the collection body) and conditional requests (using `ETag`, `If-Match`, `If-None-Match` for caching and optimistic concurrency control).
*   **Potential Benefits**: More robust API interactions, better caching, reduced data transfer, and improved handling of concurrent updates.
*   **Affected Components**: `CollectionJsonRepresentor` (for adding Link headers), middleware or service layer (for ETag generation/validation), potentially `cj_models.py` (to carry ETag info).

## 5. Client-Side Validation based on Template/Query Data Constraints

*   **Description**: `QueryData` and `TemplateData` can define constraints like `pattern`, `min_length`, `required`, etc. While basic HTML5 validation is present, this feature would enhance it with client-side JavaScript for more immediate and user-friendly feedback (e.g., custom messages, error highlighting) before form submission.
*   **Potential Benefits**: Improved user experience in forms, reduced server-side load by catching errors earlier, clearer communication of input requirements.
*   **Affected Components**: `cj_template.html` (JavaScript for advanced validation).
