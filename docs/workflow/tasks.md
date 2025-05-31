Okay, here's a granular step-by-step MVP plan to build the RESTful workflow service backend, designed for an engineering LLM to complete one task at a time. Each task is small, testable, and focuses on a single concern.

**Phase 1: Core Job Definition, Submission, and Retrieval (No Execution)**

* **Task 1.1: Define Basic JobInstance Data Model (In-Memory)**
    * **Start**: No `JobInstance` model exists.
    * **Action**: Define a simple in-memory data structure (e.g., a class or dictionary/map) for `JobInstance`.
        * Include fields: `jobID` (string, UUID), `description` (string), `jobStatus` (string, default "defined"), `dateCreated` (timestamp), `jobDefinition` (object/string, to hold the raw submitted job definition).
    * **End**: `JobInstance` model is defined and can be instantiated in code.
    * **Test**: Create an instance of the `JobInstance` model programmatically and verify its fields can be set and read.

* **Task 1.2: Implement In-Memory JobInstance Store (Singleton)**
    * **Start**: No storage mechanism for `JobInstance` exists.
    * **Action**: Create a singleton class or module that will act as an in-memory store for `JobInstance` objects.
        * Implement methods: `addJob(jobInstance)`, `getJobByID(jobID)`. Use a simple dictionary/map internally to store jobs keyed by `jobID`.
    * **End**: `JobInstanceStore` can store and retrieve `JobInstance` objects by `jobID`.
    * **Test**: Programmatically add a `JobInstance` to the store, then retrieve it by its `jobID` and verify the retrieved object matches the original. Test retrieving a non-existent `jobID` (should return null/undefined or an error).

* **Task 1.3: Create API Endpoint - `POST /jobs` (Submit Job)**
    * **Start**: No API endpoint for job submission.
    * **Action**: Create the `POST /jobs` HTTP endpoint.
        * It should accept a JSON request body (representing the `jobDefinition`).
        * Generate a new `jobID` (UUID).
        * Create a `JobInstance` with status "defined", the current `dateCreated`, the provided `jobDefinition`, and the generated `jobID`.
        * Store the `JobInstance` in the `JobInstanceStore`.
        * Respond with `201 Created`.
        * `Location` header: `/jobs/{jobID}`.
        * Response Body: The created `JobInstance` object.
    * **End**: Jobs can be submitted via HTTP, stored, and a success response returned.
    * **Test**: Send a POST request with a sample JSON body to `/jobs`. Verify a `201` status, the `Location` header, and that the response body contains the job with a generated `jobID` and status "defined". Check the in-memory store to confirm the job is present.

* **Task 1.4: Create API Endpoint - `GET /jobs/{jobID}` (Read Job)**
    * **Start**: No API endpoint to retrieve a specific job.
    * **Action**: Create the `GET /jobs/{jobID}` HTTP endpoint.
        * Retrieve the `JobInstance` from the `JobInstanceStore` using the `jobID` from the path.
        * If found, respond with `200 OK` and the `JobInstance` object in the body.
        * If not found, respond with `404 Not Found`.
    * **End**: A specific job can be retrieved via HTTP using its `jobID`.
    * **Test**:
        1.  Submit a job using `POST /jobs`.
        2.  Use the returned `jobID` to make a GET request to `/jobs/{jobID}`. Verify `200 OK` and the correct job data.
        3.  Make a GET request to `/jobs/{nonExistentJobID}`. Verify `404 Not Found`.

**Phase 2: Minimal Job & Task State Transition (No Real Task Logic)**

* **Task 2.1: Define Basic TaskInstance Data Model (In-Memory, part of JobInstance)**
    * **Start**: `JobInstance` model does not include tasks.
    * **Action**: Modify the `JobInstance` model to include a list/array called `tasks`.
        * Define a simple in-memory data structure for `TaskInstance` within `JobInstance`.
        * Include fields for `TaskInstance`: `taskID` (string, can be an index or simple ID for now), `taskDescription` (string), `taskStatus` (string, default "pending").
        * When a job is submitted (`POST /jobs`), parse a predefined simple task structure from the `jobDefinition` (e.g., `jobDefinition: { tasks: [{description: "mock task"}] }`) and populate the `tasks` list in `JobInstance`.
    * **End**: `JobInstance` now contains a list of `TaskInstance` objects, initialized from the job definition.
    * **Test**: Submit a job with a predefined task in its definition. Retrieve the job and verify the `tasks` list is populated correctly with "pending" tasks.

* **Task 2.2: Basic Workflow Execution Engine Stub (Changes Job & Task Statuses)**
    * **Start**: No job execution logic.
    * **Action**: Create a stub for the `WorkflowExecutionEngine`. For this MVP, it can be a simple function that is *manually triggered* (or triggered after job submission if simple enough, but for testing, manual might be better initially).
        * Method: `executeJob(jobID)`.
        * It retrieves the `JobInstance` from the `JobInstanceStore`.
        * If `jobStatus` is "defined":
            1.  Change `jobStatus` to "working", `taskStatus` of the first task to "working".
            2.  *(Simulate task execution)*: Immediately change `taskStatus` of the first task to "completed".
            3.  Change `jobStatus` to "completed".
            4.  Update `dateUpdated` timestamp for the job.
    * **End**: The engine can transition a job and its first (mock) task through states: defined -> working -> completed.
    * **Test**:
        1.  Submit a job (`POST /jobs`). Its status is "defined", task status is "pending".
        2.  Manually call `executeJob(jobID)`.
        3.  Retrieve the job (`GET /jobs/{jobID}`). Verify `jobStatus` is "completed" and the first task's `taskStatus` is "completed".

* **Task 2.3: Modify `POST /jobs` to Set Initial Status to "pending"**
    * **Start**: `POST /jobs` creates jobs with status "defined".
    * **Action**: Modify the `POST /jobs` endpoint.
        * When a `JobInstance` is created, set its `jobStatus` to "pending" instead of "defined".
        * Tasks should still be initialized with "pending" status.
    * **End**: New jobs are created with `jobStatus` "pending".
    * **Test**: Submit a job via `POST /jobs`. Retrieve it and verify `jobStatus` is "pending".

* **Task 2.4: Enhance Workflow Execution Engine Stub for "pending" Jobs**
    * **Start**: Engine stub looks for "defined" jobs.
    * **Action**: Modify the `WorkflowExecutionEngine`'s `executeJob(jobID)` method.
        * It retrieves the `JobInstance`.
        * If `jobStatus` is "pending":
            1.  Change `jobStatus` to "working". Update `dateUpdated`.
            2.  If tasks exist, change the first `taskStatus` to "working".
            3.  *(Simulate task execution)*: Log "Executing mock task {taskID} for job {jobID}".
            4.  If tasks exist, change the first `taskStatus` to "completed".
            5.  Change `jobStatus` to "completed". Update `dateUpdated`.
    * **End**: The engine processes jobs starting from "pending" status.
    * **Test**:
        1.  Submit a job (`POST /jobs`). Status is "pending".
        2.  Manually call `executeJob(jobID)`.
        3.  Retrieve the job (`GET /jobs/{jobID}`). Verify `jobStatus` is "completed", and the first task is "completed".

**Phase 3: Basic Progress Tracking**

* **Task 3.1: Implement API Endpoint - `GET /jobs/{jobID}/progress`**
    * **Start**: No endpoint to view job progress.
    * **Action**: Create the `GET /jobs/{jobID}/progress` HTTP endpoint.
        * Retrieve the `JobInstance` (which includes tasks) from the `JobInstanceStore`.
        * If found, respond with `200 OK`.
        * The response body should be a simplified progress view:
            ```json
            {
              "jobID": "...",
              "jobStatus": "...",
              "dateCreated": "...",
              "dateUpdated": "...",
              "tasks": [
                { "taskID": "...", "taskDescription": "...", "taskStatus": "..." }
              ]
            }
            ```
        * If job not found, respond with `404 Not Found`.
    * **End**: Job progress can be queried via HTTP.
    * **Test**:
        1.  Submit a job.
        2.  Call `executeJob(jobID)`.
        3.  Make a GET request to `/jobs/{jobID}/progress`. Verify `200 OK` and the response shows the "completed" status for the job and task.
        4.  Test with a job that hasn't been "executed" yet (status "pending"). Verify the progress reflects this.

**Phase 4: Basic Shared State Management (No Task Interaction With It Yet)**

* **Task 4.1: Modify `JobInstance` to include `sharedStateURL` and `sharedState` data**
    * **Start**: `JobInstance` has no concept of shared state.
    * **Action**:
        * Add `sharedStateURL` (string) and `sharedState` (object) to the `JobInstance` model.
        * In `POST /jobs`, when a job is created:
            * Set `sharedStateURL` to `/jobs/{jobID}/shared-state`.
            * Initialize `sharedState` from an optional `initialSharedState` field in the request body, or to an empty object `{}` if not provided.
    * **End**: `JobInstance` holds shared state data and a URL to access it.
    * **Test**: Submit a job with and without `initialSharedState`. Retrieve the job and verify `sharedStateURL` is correctly formed and `sharedState` is initialized.

* **Task 4.2: Implement API Endpoint - `GET /jobs/{jobID}/shared-state`**
    * **Start**: No endpoint to view a job's shared state.
    * **Action**: Create the `GET /jobs/{jobID}/shared-state` HTTP endpoint.
        * Retrieve the `JobInstance` from the `JobInstanceStore`.
        * If found, respond with `200 OK` and the `jobInstance.sharedState` object in the body.
        * If not found, respond with `404 Not Found`.
    * **End**: A job's shared state can be retrieved via HTTP.
    * **Test**: Submit a job with `initialSharedState`. Make a GET request to its `sharedStateURL`. Verify `200 OK` and the correct shared state data.

* **Task 4.3: Implement API Endpoint - `PUT /jobs/{jobID}/shared-state`**
    * **Start**: No endpoint to update a job's shared state.
    * **Action**: Create the `PUT /jobs/{jobID}/shared-state` HTTP endpoint.
        * Retrieve the `JobInstance` from the `JobInstanceStore`.
        * If found:
            * Replace the `jobInstance.sharedState` with the request body.
            * Update `jobInstance.dateUpdated`.
            * Respond with `200 OK` and the updated `jobInstance.sharedState`.
        * If not found, respond with `404 Not Found`.
    * **End**: A job's shared state can be updated via HTTP.
    * **Test**: Submit a job. Update its shared state using `PUT` to its `sharedStateURL`. Retrieve the shared state again using `GET` and verify it has been updated.

**Phase 5: Basic Internal Task Execution Logic Interacting with Shared State**

* **Task 5.1: Define a Simple Internal Task Logic Function**
    * **Start**: No actual task logic beyond status changes.
    * **Action**: Create a simple function within the backend (not an external service).
        * Example function: `incrementCounterTask(currentSharedState)`
            * Takes the current shared state object as input.
            * Reads a property (e.g., `currentSharedState.counter`, defaults to 0 if not present).
            * Increments it.
            * Updates the property in the shared state object (e.g., `currentSharedState.counter = newValue`).
            * Returns the modified shared state.
    * **End**: A testable internal function exists that can modify a shared state object.
    * **Test**: Call the function directly with a sample shared state object and verify the returned state is correctly modified.

* **Task 5.2: Basic TaskExecutor Stub**
    * **Start**: No `TaskExecutor` component.
    * **Action**: Create a `TaskExecutor` stub.
        * Method: `executeTask(taskInstance, currentSharedState)`
        * For now, this method will specifically call the `incrementCounterTask` if `taskInstance.taskDescription` (or a new `taskType` field) indicates it's that type of task.
        * It should return the new shared state.
    * **End**: `TaskExecutor` can be called to invoke the internal task logic.
    * **Test**: Call `TaskExecutor.executeTask` with a mock task and shared state. Verify it returns the modified shared state from `incrementCounterTask`.

* **Task 5.3: Integrate TaskExecutor into WorkflowExecutionEngine**
    * **Start**: `WorkflowExecutionEngine` only simulates task execution.
    * **Action**: Modify the `WorkflowExecutionEngine.executeJob(jobID)` method.
        * When "executing" a task:
            1.  Retrieve the current `jobInstance.sharedState`.
            2.  Call `TaskExecutor.executeTask(taskInstance, currentSharedState)`.
            3.  Update `jobInstance.sharedState` with the state returned by the `TaskExecutor`.
            4.  Update `jobInstance.dateUpdated`.
    * **End**: The engine now uses the `TaskExecutor` to modify the job's shared state based on task logic.
    * **Test**:
        1.  Submit a job with `initialSharedState: { "counter": 5 }` and a task definition that the `TaskExecutor` recognizes as the `incrementCounterTask`.
        2.  Manually call `executeJob(jobID)`.
        3.  Retrieve the job's shared state (`GET /jobs/{jobID}/shared-state`). Verify that `counter` is now `6`.
        4.  Check the progress (`GET /jobs/{jobID}/progress`) to ensure job and task statuses are "completed".

This MVP provides a basic end-to-end flow: submitting a job with initial data, having an internal "engine" process a mock/simple task that modifies this data, and being able to query the job's status and its data. It sets the stage for adding more complex features like actual external service calls, more sophisticated JCL, and error handling.
