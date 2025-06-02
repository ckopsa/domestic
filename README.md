## Running Tests with Docker Compose

This project uses a separate Docker Compose setup to run tests against a dedicated test database.

1.  **Ensure Docker is running.**

2.  **Build the test environment (if not already built or if changes were made):**
    ```bash
    docker-compose -f docker-compose.test.yml build
    ```

3.  **Start the test services (Postgres and API):**
    ```bash
    docker-compose -f docker-compose.test.yml up -d
    ```
    The `-d` flag runs the services in detached mode.

4.  **Run the tests:**
    The tests are executed using `pytest` inside the `api_test` container.
    ```bash
    docker-compose -f docker-compose.test.yml exec api_test pytest app/tests
    ```
    You can also run specific test files or use other pytest arguments:
    ```bash
    docker-compose -f docker-compose.test.yml exec api_test pytest app/tests/test_api_endpoints.py
    ```

5.  **View logs (optional):**
    To view the logs from the test services:
    ```bash
    docker-compose -f docker-compose.test.yml logs -f api_test postgres_test
    ```

6.  **Stop and remove the test services when done:**
    ```bash
    docker-compose -f docker-compose.test.yml down
    ```
    To also remove the test database volume (if you want a completely clean slate next time):
    ```bash
    docker-compose -f docker-compose.test.yml down -v
    ```

The `test.env` file in the root directory provides the default configuration for the test database.
The `api_test` service will be available on host port `5001` and the `postgres_test` service on host port `5433` if you need to connect to them directly, though this is generally not required for running tests.
