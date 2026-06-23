#!/usr/bin/env python3
"""
WaterServicesNewsTracker – filtered RSS + HTML collectors
Version: 1.0
"""
import os
import re
import csv
import html
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urljoin

BASE_DIR = os.path.join(os.getcwd(), 'WaterServicesNewsTracker')
DATE_STAMP = datetime.now(timezone.utc).strftime('%Y-%m-%d')
METADATA_FILE = os.path.join(BASE_DIR, f'metadata-{DATE_STAMP}.csv')
MAX_AGE_DAYS = 2

PRIMARY_KEYWORDS = [
    'water services','wastewater','stormwater','drinking water','water quality',
    'three waters','water services reform','water infrastructure','water supply'
]

SECONDARY_KEYWORDS = [
    'infrastructure funding','network failure','environmental limits','overflow','contamination','public health risk',
    'nitrates','heavy metals','climate change','leak','leakage','pipe burst','service disruption','biosolids','pipes',
    'taumata arowai','water services authority','standards','discharge','drought','extreme rainfall','flood resilience','sea level rise'
]

EXCLUDE_KEYWORDS = [
    'murder','homicide','stabbing','shooting','assault','police','body','death','court','trial','sentenced',
    'swimming','surf','beach','fishing','boating','kayak','travel','tourism','holiday','destination',
    'forecast','weather','rainfall','showers','thunderstorm','temperature',
    'hydro','hydroelectric','electricity','power generation'
]

RSS_FEEDS = [
    'https://www.rnz.co.nz/rss/environment.xml',
    'https://www.rnz.co.nz/rss/national.xml',
    'https://newsroom.co.nz/feed/',
    'https://www.stuff.co.nz/rss',
    'https://www.nzherald.co.nz/arc/outboundfeeds/rss/curated/78/?outputType=xml&_website=nzh',
    'https://www.nzherald.co.nz/arc/outboundfeeds/rss/section/environment/?outputType=xml&_website=nzh',
    'https://www.nzherald.co.nz/arc/outboundfeeds/rss/section/business/?outputType=xml&_website=nzh'
]

HTML_SOURCES = [
    ('https://thespinoff.co.nz/science','The Spinoff'),
    ('https://thespinoff.co.nz/tags/water','The Spinoff'),
    ('https://www.taumataarowai.govt.nz/home/articles','Taumata Arowai'),
    ('https://environment.govt.nz/news/','MfE'),
    ('https://www.lgnz.co.nz/news/','LGNZ'),
    ('https://www.teurukahika.govt.nz/news-and-publications','Te Uru Kahika'),
    ('https://www.stuff.co.nz/environment','Stuff Environment')
]

HEADERS = {'User-Agent': 'WaterServicesTracker/1.0'}

PRIMARY_PATTERNS = [re.compile(rf"\b{re.escape(k)}\b", re.I) for k in PRIMARY_KEYWORDS]
SECONDARY_PATTERNS = [re.compile(rf"\b{re.escape(k)}\b", re.I) for k in SECONDARY_KEYWORDS]
EXCLUDE_PATTERNS = [re.compile(rf"\b{re.escape(k)}\b", re.I) for k in EXCLUDE_KEYWORDS]


def normalize(text):
    if not text:
        return ''
    text = BeautifulSoup(text, 'html.parser').get_text(' ')
    text = html.unescape(text).lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def match_item(title, summary):
    t = normalize(title)
    s = normalize(summary)
    combined = t + ' ' + s

    if any(p.search(combined) for p in EXCLUDE_PATTERNS):
        return False

    primary = any(p.search(combined) for p in PRIMARY_PATTERNS)
    secondary = any(p.search(combined) for p in SECONDARY_PATTERNS)

    return primary and (secondary or primary)


def age_ok(published):
    if not published:
        return True
    return (datetime.now(timezone.utc) - published) <= timedelta(days=MAX_AGE_DAYS)


def fetch_rss():
    articles = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.get('title','')
            summary = entry.get('summary','')
            link = entry.get('link','')
            published = None

            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            if not age_ok(published):
                continue
            if not match_item(title, summary):
                continue

            articles.append([title, link, published.isoformat() if published else '', url])
    return articles


def fetch_html():
    results = []
    for url, source in HTML_SOURCES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.select('article h2 a, article h3 a, a[href]'):
                raw_title = a.get_text(strip=True)
                # Clean out common trailing elements (author, date, etc.)
                title = re.split(r'\\b(By|\\|)\\b', raw_title)[0].strip()

                link = urljoin(url, a.get('href'))
                # Try to find a nearby date
                published = None
                time_tag = a.find_parent().find('time')
                if time_tag and time_tag.has_attr('datetime'):
                    try:
                        published = datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00'))
                    except Exception:
                        published = None

               if not age_ok(published):
                   continue

                summary = ''
                if not match_item(title, summary):
                    continue
                results.append([title, link, '', source])
        except Exception:
            continue
    return results


def write_csv(items):
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(METADATA_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['title','link','date','source'])
        writer.writerows(items)


if __name__ == '__main__':
    data = []
    data.extend(fetch_rss())
    data.extend(fetch_html())
    write_csv(data)
