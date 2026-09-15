"""Fetches a sitemap.xml (urlset or sitemapindex, recursing into the latter)
and returns a flat list of page URLs. No filtering of what's "worth"
ingesting — that decision belongs to the caller (see crawl_site.py)."""

import xml.etree.ElementTree as ET

import requests

SITEMAP_NAMESPACE = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def fetch_sitemap_urls(sitemap_url: str, timeout: int = 15) -> list[str]:
    response = requests.get(sitemap_url, timeout=timeout)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    root_tag = root.tag.split("}")[-1]

    if root_tag == "sitemapindex":
        urls = []
        for sitemap_el in root.findall("sm:sitemap", SITEMAP_NAMESPACE):
            loc = sitemap_el.find("sm:loc", SITEMAP_NAMESPACE)
            if loc is not None and loc.text:
                urls.extend(fetch_sitemap_urls(loc.text.strip(), timeout=timeout))
        return urls

    return [
        loc.text.strip()
        for url_el in root.findall("sm:url", SITEMAP_NAMESPACE)
        for loc in [url_el.find("sm:loc", SITEMAP_NAMESPACE)]
        if loc is not None and loc.text
    ]
