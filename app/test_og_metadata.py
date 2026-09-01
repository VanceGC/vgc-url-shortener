import unittest
from unittest.mock import patch

from og_metadata import OpenGraphParser, fetch_open_graph, is_preview_crawler, validate_http_url


class FakeResponse:
    is_redirect = False
    is_permanent_redirect = False
    encoding = 'utf-8'
    headers = {'Content-Type': 'text/html; charset=utf-8'}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        del chunk_size
        yield b'''<html><head>
            <meta property="og:title" content="Example title">
            <meta property="og:description" content="Example description">
            <meta property="og:image" content="/preview.jpg">
        </head></html>'''

    def close(self):
        return None


class OpenGraphTests(unittest.TestCase):
    def test_parser_falls_back_to_document_title(self):
        parser = OpenGraphParser()
        parser.feed('<title>  A useful title  </title>')
        self.assertEqual(parser.document_title, 'A useful title')

    def test_rejects_non_http_urls(self):
        with self.assertRaises(ValueError):
            validate_http_url('javascript:alert(1)')

    def test_metadata_fetch_rejects_private_networks(self):
        with self.assertRaisesRegex(ValueError, 'public IP'):
            fetch_open_graph('http://127.0.0.1/private')

    def test_detects_social_preview_crawlers(self):
        self.assertTrue(is_preview_crawler('Twitterbot/1.0'))
        self.assertFalse(is_preview_crawler('Mozilla/5.0'))

    @patch('og_metadata._assert_public_hostname')
    @patch('og_metadata.requests.get', return_value=FakeResponse())
    def test_fetches_metadata_and_resolves_relative_images(self, _get, _hostname):
        metadata = fetch_open_graph('https://example.com/article')
        self.assertEqual(metadata['title'], 'Example title')
        self.assertEqual(metadata['description'], 'Example description')
        self.assertEqual(metadata['image'], 'https://example.com/preview.jpg')


if __name__ == '__main__':
    unittest.main()
