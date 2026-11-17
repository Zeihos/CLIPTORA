"""Check that the local-only editor cannot be driven through hostile Host headers."""
import http.client
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server


class LocalHTTPGuardTests(unittest.TestCase):
    def setUp(self):
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        # Cleanup handlers are LIFO: stop the server before joining the thread.
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    def _get(self, host):
        req = Request(f'http://127.0.0.1:{self.http.server_port}/', headers={'Host': host})
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    def _post(self, host, content_length='2'):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        self.addCleanup(conn.close)
        conn.putrequest('POST', '/api/scan', skip_host=True)
        conn.putheader('Host', host)
        conn.putheader('Content-Type', 'application/json')
        conn.putheader('Content-Length', content_length)
        conn.endheaders(b'{}' if content_length == '2' else None)
        response = conn.getresponse()
        status = response.status
        data = response.read()
        return status, data

    def test_rejects_foreign_host_on_get(self):
        status, data = self._get(f'attacker.example:{self.http.server_port}')
        self.assertEqual(status, 403)
        self.assertIn(b'error', data)

    def test_rejects_foreign_host_before_post_mutations(self):
        status, data = self._post(f'attacker.example:{self.http.server_port}')
        self.assertEqual(status, 403)
        self.assertIn(b'error', data)

    def test_accepts_loopback_host_with_current_port(self):
        for host in (f'127.0.0.1:{self.http.server_port}', f'localhost:{self.http.server_port}'):
            with self.subTest(host=host):
                status, html = self._get(host)
                self.assertEqual(status, 200)
                self.assertIn(b'CLIPTORA', html)

    def test_entire_large_media_is_returned_without_range_header(self):
        # Browser fetches may begin without Range; a 200 response must not
        # silently stop at the range-chunk limit of four MiB.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.mp4'
            payload = b'A' * (4 * 1024 * 1024 + 71)
            path.write_bytes(payload)
            fake = SimpleNamespace(project={
                'source_dir': directory,
                'files': [{'id': 'sample', 'path': str(path)}],
            })
            with patch.object(server, 'studio', fake):
                url = f'http://127.0.0.1:{self.http.server_port}/media?id=sample'
                with urlopen(url, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(int(response.headers['Content-Length']), len(payload))
                    self.assertEqual(response.read(), payload)

    def test_invalid_byte_range_returns_416(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.mp4'
            path.write_bytes(b'abc123')
            fake = SimpleNamespace(project={
                'source_dir': directory,
                'files': [{'id': 'sample', 'path': str(path)}],
            })
            with patch.object(server, 'studio', fake):
                url = f'http://127.0.0.1:{self.http.server_port}/media?id=sample'
                req = Request(url, headers={'Range': 'bytes=4-2'})
                with self.assertRaises(HTTPError) as caught:
                    urlopen(req, timeout=5)
                self.assertEqual(caught.exception.code, 416)

    def test_rejects_malformed_content_length(self):
        host = f'127.0.0.1:{self.http.server_port}'
        for length in ('-1', 'not-a-number'):
            with self.subTest(length=length):
                status, data = self._post(host, length)
                self.assertEqual(status, 400)
                self.assertIn(b'error', data)


if __name__ == '__main__':
    unittest.main()
