import pytest
from unittest.mock import patch, MagicMock
import sys

# We need to make sure we can import pdf_utils
# It's in the root, so it should be fine if we run pytest from root.

def test_paddle_engine_singleton():
    """Verify that get_paddle_engine returns the same instance and initializes only once."""

    # Import pdf_utils to access the module
    import pdf_utils

    # Check if the function exists (it won't initially)
    if not hasattr(pdf_utils, 'get_paddle_engine'):
        pytest.fail("get_paddle_engine not implemented yet")

    # Reset the singleton if it exists (for test isolation)
    if hasattr(pdf_utils, '_PADDLE_ENGINE'):
        pdf_utils._PADDLE_ENGINE = None

    # Patch PPStructure inside pdf_utils
    with patch('pdf_utils.PPStructure') as MockPPStructure:
        # Setup the mock to return a specific instance
        mock_instance = MagicMock()
        MockPPStructure.return_value = mock_instance

        # First call - should initialize
        engine1 = pdf_utils.get_paddle_engine()

        # Second call - should return cached
        engine2 = pdf_utils.get_paddle_engine()

        # Assertions
        assert engine1 is engine2, "get_paddle_engine should return the same instance"
        assert engine1 is mock_instance, "Should return the mocked instance"

        # Verify constructor called only once
        MockPPStructure.assert_called_once()
