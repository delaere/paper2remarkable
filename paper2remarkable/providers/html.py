# -*- coding: utf-8 -*-

"""Provider for HTML documents

This provider is a little bit special, in that it isn't simply pulling an 
academic paper from a site, but instead aims to pull a HTML article.

Author: G.J.J. van den Burg
License: See LICENSE file.
Copyright: 2020, G.J.J. van den Burg

"""

import html2text
import markdown
import readability
import titlecase
import unidecode
import urllib
import weasyprint
import weasyprint.fonts

from ._base import Provider
from ._info import Informer

from ..utils import (
    clean_string,
    get_page_with_retry,
    get_content_type_with_retry,
)
from ..log import Logger

logger = Logger()

CSS = """
@import url('https://fonts.googleapis.com/css?family=EB+Garamond|Noto+Serif|Inconsolata&display=swap');
@page { size: 702px 936px; margin: 1in; }
a { color: black; }
img { display: block; margin: 0 auto; text-align: center; max-width: 70%; max-height: 300px; }
p, li { font-size: 10pt; font-family: 'EB Garamond'; hyphens: auto; text-align: justify; }
h1,h2,h3 { font-family: 'Noto Serif'; }
h1 { font-size: 26px; }
h2 { font-size: 18px; }
h3 { font-size: 14px; }
blockquote { font-style: italic; }
pre { font-family: 'Inconsolata'; padding-left: 2.5%; background: #efefef; }
code { font-family: 'Inconsolata'; font-size: .7rem; background: #efefef; }
"""


def my_fetcher(url):
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("file:///"):
        url = "https:" + url[len("file:/") :]
    return weasyprint.default_url_fetcher(url)


class HTMLInformer(Informer):
    def __init__(self):
        super().__init__()

    def get_filename(self, abs_url):
        request_text = get_page_with_retry(abs_url, return_text=True)
        doc = readability.Document(request_text)
        title = doc.title()

        # Clean the title and make it titlecase
        title = clean_string(title)
        title = titlecase.titlecase(title)
        title = title.replace(" ", "_")
        title = clean_string(title)
        name = title.strip("_") + ".pdf"
        name = unidecode.unidecode(name)
        logger.info("Created filename: %s" % name)
        return name


class HTML(Provider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.informer = HTMLInformer()

    def get_abs_pdf_urls(self, url):
        return url, url

    def retrieve_pdf(self, pdf_url, filename):
        """Turn the HTML article in a clean pdf file"""
        # Steps
        # 1. Pull the HTML page using requests
        # 2. Extract the article part of the page using readability
        # 3. Convert the article HTML to markdown using html2text
        # 4. Convert the markdown back to HTML (this is done to sanitize HTML)
        # 4. Convert the HTML to PDF, pulling in images where needed
        # 5. Save the PDF to the specified filename.
        request_text = get_page_with_retry(pdf_url, return_text=True)
        doc = readability.Document(request_text)
        title = doc.title()
        raw_html = doc.summary(html_partial=True)

        h2t = html2text.HTML2Text()
        h2t.wrap_links = False
        text = h2t.handle(raw_html)

        # Add the title back to the document
        article = "# {title}\n\n{text}".format(title=title, text=text)

        # fix relative urls
        base_url = "{0.scheme}://{0.netloc}".format(
            urllib.parse.urlsplit(pdf_url)
        )
        html_article = markdown.markdown(article)
        html_article = html_article.replace(' src="//', ' src="https://')
        html_article = html_article.replace(
            ' src="/', ' src="{base}/'.format(base=base_url)
        )

        if self.debug:
            with open("./paper.html", "w") as fp:
                fp.write(html_article)

        font_config = weasyprint.fonts.FontConfiguration()
        html = weasyprint.HTML(string=html_article, url_fetcher=my_fetcher)
        css = weasyprint.CSS(string=CSS, font_config=font_config)

        html.write_pdf(filename, stylesheets=[css], font_config=font_config)

    def validate(src):
        # first check if it is a valid url
        parsed = urllib.parse.urlparse(src)
        if not all([parsed.scheme, parsed.netloc, parsed.path]):
            return False
        # next, get the header and check the content type
        ct = get_content_type_with_retry(src)
        if ct is None:
            return False
        return ct.startswith("text/html")
