from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import ipaddress
import re
import socket

import requests


MAX_HTML_BYTES = 1_000_000
MAX_REDIRECTS = 5
PREVIEW_BOT_PATTERN = re.compile(
    r"bot|crawler|spider|facebookexternalhit|facebot|twitterbot|linkedinbot|"
    r"slackbot|discordbot|whatsapp|telegrambot|pinterest|skypeuripreview|"
    r"google-inspectiontool|applebot",
    re.IGNORECASE,
)


class OpenGraphParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadata = {}
        self.title_parts = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attributes = {key.lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            content = attributes.get("content", "").strip()
            if key and content and key not in self.metadata:
                self.metadata[key] = content
        elif tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)

    @property
    def document_title(self):
        return " ".join("".join(self.title_parts).split())


def validate_http_url(value):
    if not isinstance(value, str):
        raise ValueError("URL must be a string")

    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must begin with http:// or https://")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not supported")
    return value


def _assert_public_hostname(hostname):
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise ValueError("Destination hostname could not be resolved") from exc

    if not addresses:
        raise ValueError("Destination hostname could not be resolved")

    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("Destination must use a public IP address")


def _safe_fetch_url(value):
    value = validate_http_url(value)
    _assert_public_hostname(urlparse(value).hostname)
    return value


def fetch_open_graph(value, timeout=6):
    current_url = _safe_fetch_url(value)
    headers = {
        "User-Agent": "VGC.to Open Graph Fetcher/1.0",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
    }

    for _ in range(MAX_REDIRECTS + 1):
        response = requests.get(
            current_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise ValueError("Destination returned an invalid redirect")
            current_url = _safe_fetch_url(urljoin(current_url, location))
            continue

        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            response.close()
            raise ValueError("Destination did not return an HTML page")

        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=16_384):
            total += len(chunk)
            if total > MAX_HTML_BYTES:
                response.close()
                raise ValueError("Destination HTML is too large to inspect")
            chunks.append(chunk)

        encoding = response.encoding or "utf-8"
        html = b"".join(chunks).decode(encoding, errors="replace")
        response.close()

        parser = OpenGraphParser()
        parser.feed(html)
        metadata = parser.metadata

        image = metadata.get("og:image") or metadata.get("twitter:image") or ""
        return {
            "title": metadata.get("og:title") or metadata.get("twitter:title") or parser.document_title,
            "description": (
                metadata.get("og:description")
                or metadata.get("twitter:description")
                or metadata.get("description")
                or ""
            ),
            "image": urljoin(current_url, image) if image else "",
        }

    raise ValueError("Destination redirected too many times")


def is_preview_crawler(user_agent):
    return bool(PREVIEW_BOT_PATTERN.search(user_agent or ""))
