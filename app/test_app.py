import unittest
from unittest.mock import patch

from app import URLMap, app, db


class AppOpenGraphTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
        with self.client.session_transaction() as session:
            session['logged_in'] = True

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_custom_metadata_is_served_to_preview_crawlers(self):
        response = self.client.post('/api/shorten', json={
            'url': 'https://example.com/article',
            'custom_alias': 'custom-og',
            'label': 'Example',
            'og_mode': 'custom',
            'og_title': 'Custom preview title',
            'og_description': 'Custom preview description',
            'og_image': 'https://example.com/preview.jpg'
        })
        self.assertEqual(response.status_code, 201)

        preview = self.client.get('/custom-og', headers={'User-Agent': 'Twitterbot/1.0'})
        self.assertEqual(preview.status_code, 200)
        self.assertIn(b'Custom preview title', preview.data)
        self.assertIn(b'property="og:image"', preview.data)

        with app.app_context():
            self.assertEqual(URLMap.query.filter_by(short='custom-og').one().click_count, 0)

        redirect = self.client.get('/custom-og', headers={'User-Agent': 'Mozilla/5.0'})
        self.assertEqual(redirect.status_code, 302)
        self.assertEqual(redirect.location, 'https://example.com/article')
        with app.app_context():
            self.assertEqual(URLMap.query.filter_by(short='custom-og').one().click_count, 1)

    @patch('app.fetch_open_graph', return_value={
        'title': 'Destination title',
        'description': 'Destination description',
        'image': 'https://example.com/destination.jpg'
    })
    def test_destination_metadata_is_the_default(self, fetch):
        response = self.client.post('/api/shorten', json={
            'url': 'https://example.com/article',
            'custom_alias': 'destination-og'
        })
        self.assertEqual(response.status_code, 201)
        fetch.assert_called_once_with('https://example.com/article')

        with app.app_context():
            link = URLMap.query.filter_by(short='destination-og').one()
            self.assertEqual(link.og_mode, 'destination')
            self.assertEqual(link.og_title, 'Destination title')


if __name__ == '__main__':
    unittest.main()
