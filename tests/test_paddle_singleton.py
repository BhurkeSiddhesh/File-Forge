import sys
import unittest
from unittest.mock import patch, MagicMock
import scripts.pdf_utils as pdf_utils

try:
    import paddleocr  # noqa: F401
except ImportError:
    # paddleocr is a heavy optional dependency; stub it so PPStructure can be
    # patched in environments where it isn't installed (e.g. lightweight CI).
    sys.modules["paddleocr"] = MagicMock()

class TestPaddleSingleton(unittest.TestCase):
    def setUp(self):
        # Reset the singleton before each test
        pdf_utils._PADDLE_ENGINE = None

    @patch('paddleocr.PPStructure', create=True)
    def test_get_paddle_engine_singleton(self, mock_ppstructure):
        # Configure the mock to return a dummy object
        mock_instance = MagicMock()
        mock_ppstructure.return_value = mock_instance

        # First call: should initialize
        engine1 = pdf_utils.get_paddle_engine()

        # Second call: should return the same instance
        engine2 = pdf_utils.get_paddle_engine()

        # Check that they are the same object
        self.assertIs(engine1, engine2)

        # Check that PPStructure was initialized only once
        mock_ppstructure.assert_called_once()

        # Check that the returned object is what the mock returned
        self.assertIs(engine1, mock_instance)

if __name__ == '__main__':
    unittest.main()
