# tests/conftest.py
import pytest
import os
from app import create_app as main_app # Adjust this import

@pytest.fixture(scope='session') # 'session' scope means it runs once per test session
def app():
    """Create and configure a new app instance for each test session."""
    # Set the TESTING flag to True
    main_app.config.update({
        "TESTING": True,
        "AUDIO_DIR": "test_audio_files",  # Use a temporary/test audio directory
        # Add other test-specific configurations:
        # For example, if you use an API key, you might use a mock key or disable the API
        # "TRANSLATION_API_KEY": "test_key_abc",
        # "VOSK_MODEL_PATH": "mock/vosk/model/path" # If you load models based on config
    })

    # Ensure the test audio directory exists
    os.makedirs(main_app.config["AUDIO_DIR"], exist_ok=True)

    # You can also set up and tear down database connections here if you had them.
    # For example, create an in-memory SQLite database for tests.

    yield main_app # This is where the testing happens

    # Clean up resources after tests if needed
    # For example, remove the test_audio_files directory
    # import shutil
    # shutil.rmtree(main_app.config["AUDIO_DIR"])

@pytest.fixture()
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture()
def runner(app):
    """A test runner for CLI commands."""
    return app.test_cli_runner()