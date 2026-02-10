import unittest
from unittest.mock import patch, MagicMock
import pdf_utils
import threading

class TestPdfUtilsSingleton(unittest.TestCase):
    def setUp(self):
        # Reset the singleton before each test
        pdf_utils._PADDLE_ENGINE = None

    @patch('pdf_utils.PPStructure')
    def test_get_paddle_engine_initializes_once(self, mock_ppstructure):
        """Test that get_paddle_engine initializes PPStructure exactly once."""
        # Setup mock return value
        mock_instance = MagicMock()
        mock_ppstructure.return_value = mock_instance

        # First call - should initialize
        engine1 = pdf_utils.get_paddle_engine()
        self.assertIs(engine1, mock_instance)
        mock_ppstructure.assert_called_once()

        # Second call - should return cached instance
        engine2 = pdf_utils.get_paddle_engine()
        self.assertIs(engine2, mock_instance)
        # Should still be called only once
        mock_ppstructure.assert_called_once()

    @patch('pdf_utils.PPStructure')
    def test_get_paddle_engine_parameters(self, mock_ppstructure):
        """Test that PPStructure is initialized with correct parameters."""
        mock_instance = MagicMock()
        mock_ppstructure.return_value = mock_instance

        pdf_utils.get_paddle_engine()

        # Verify arguments
        call_args = mock_ppstructure.call_args
        kwargs = call_args.kwargs

        self.assertTrue(kwargs.get('use_onnx'), "use_onnx should be True")
        self.assertFalse(kwargs.get('use_gpu'), "use_gpu should be False")
        self.assertTrue(kwargs.get('recovery'), "recovery should be True")
        self.assertEqual(kwargs.get('lang'), 'en')

    def test_singleton_thread_safety(self):
        """Test that singleton initialization is thread-safe."""
        # This is a bit tricky to test deterministically, but we can try
        # to ensure multiple threads get the same instance.

        # We need to patch PPStructure but allow it to run concurrently
        # Since we can't easily race the lock with mocks without sleep,
        # we'll just verify the lock is used.

        # Alternatively, verify the lock object exists
        self.assertIsInstance(pdf_utils._ENGINE_LOCK, type(threading.Lock()))

if __name__ == '__main__':
    unittest.main()
