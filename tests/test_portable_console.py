"""Windows redirection defaults to a legacy codepage; Russian logs must not crash."""
import io
import unittest
from unittest.mock import patch

import server


class PortableConsoleTests(unittest.TestCase):
    def test_console_logging_accepts_russian_when_original_stream_is_cp1252(self):
        buf = io.BytesIO()
        stream = io.TextIOWrapper(buf, encoding='cp1252', errors='strict')
        with patch.object(server.sys, 'stdout', stream):
            server.configure_console_output()
            print('Для остановки нажмите Ctrl+C.', file=stream, flush=True)
            self.assertIn('Для остановки'.encode('utf-8'), buf.getvalue())


if __name__ == '__main__':
    unittest.main()
