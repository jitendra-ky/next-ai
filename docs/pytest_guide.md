# Testing Guide

This project uses an Object-Oriented Programming (OOP) approach for structuring tests, utilizing Python's built-in `unittest` framework, combined with `pytest` as our powerful and fast test runner.

## 1. Environment Setup

Before running tests, ensure you have the required dependencies installed. Our testing framework requires `pytest` and `pytest-mock` which are listed in the `requirements.txt`.

```bash
# Activate your virtual environment first
.venv\Scripts\activate

# Install all requirements
pip install -r requirements.txt
```

## 2. Test Architecture

Our tests are located inside the `tests/` directory at the root of the project.

We follow an Object-Oriented structure by inheriting from `unittest.TestCase`. This provides several benefits:
- **Encapsulation**: Tests belonging to the same component are grouped logically within a class.
- **Lifecycle Management**: Methods like `setUp()` and `tearDown()` are available to initialize or clean up state before and after each test runs.

### Example Structure

```python
import unittest
from unittest.mock import patch, Mock

class TestMyComponent(unittest.TestCase):
    def setUp(self):
        # Initialize component state here
        pass

    @patch("src.my_module.requests.get")
    def test_some_behavior(self, mock_get):
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response

        # Act & Assert
        ...
```

## 3. Running the Tests

Even though tests are written using `unittest`, we run them using `pytest` because it is faster, has better output formatting, and natively understands `unittest` classes.

To run the entire test suite, simply execute from the root directory:

```bash
pytest tests/
```

To run a specific test file:

```bash
pytest tests/test_aqi_tools.py
```

## 4. Mocking External Services

This project frequently interacts with external APIs (like OpenAQ, Nominatim, and TomTom). **Do not make real network requests during unit tests.**

Always use the `@patch` decorator from `unittest.mock` to intercept external calls. 

**Best Practices for Mocking:**
1. **Target the exact import location:** Mock the object exactly where it is used. For example, if `src/aqi_tools.py` imports `requests` and calls `requests.get`, you should patch `"src.aqi_tools.requests.get"`.
2. **Mock the response structure:** External APIs usually return JSON. Ensure your mock mimics the full response object by mocking the `.json()` method and configuring its `return_value`.
3. **Verify calls:** Use assertions like `mock_get.assert_called_once()` and verify the URL and parameters using `mock_get.call_args` to ensure the application logic passed the right arguments to the external service.
