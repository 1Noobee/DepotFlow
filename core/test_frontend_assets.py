"""
The pages must not depend on any outside website (CDN or font host): a slow or blocked
connection should never leave a depot looking at an unstyled, broken app.
"""
import logging
import re

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

EXTERNAL = re.compile(r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//""", re.I)
LOCAL_ASSETS = [
    "core/css/tailwind.css",
    "core/css/fonts.css",
    "core/vendor/alpine.min.js",
    "core/vendor/choices/choices.min.js",
    "core/vendor/choices/choices.min.css",
    "core/js/product_choices.js",
    "core/js/dynamic_formset.js",
    "core/js/stock_hint.js",
]


class FrontendAssetTests(TestCase):
    def test_pages_load_no_assets_from_outside_hosts(self):
        User.objects.create_user("u", password="S0me-long-pass-123", role=User.Role.SUPER_ADMIN)
        pages = [self.client.get(reverse("login"))]
        self.client.login(username="u", password="S0me-long-pass-123")
        pages.append(self.client.get(reverse("home")))
        pages.append(self.client.get(reverse("reports:dashboard")))
        for response in pages:
            self.assertEqual(response.status_code, 200)
            html = response.content.decode()
            self.assertIsNone(EXTERNAL.search(html), "page links to an outside host")
            for banned in ("cdn.tailwindcss.com", "cdn.jsdelivr.net", "fonts.googleapis.com",
                           "fonts.gstatic.com", "unpkg.com", 'type="text/tailwindcss"'):
                self.assertNotIn(banned, html)
            for asset in ("core/css/tailwind.css", "core/vendor/alpine.min.js"):
                self.assertIn(asset.split("/")[-1].split(".")[0], html)

    def test_every_local_asset_exists(self):
        for path in LOCAL_ASSETS:
            self.assertIsNotNone(finders.find(path), f"missing static file: {path}")

    def test_font_files_named_in_fonts_css_exist(self):
        css_path = finders.find("core/css/fonts.css")
        with open(css_path, encoding="utf-8") as fh:
            css = fh.read()
        files = re.findall(r"url\('\.\./fonts/([^']+)'\)", css)
        self.assertGreaterEqual(len(files), 15)
        self.assertEqual(css.count("@font-face"), css.count("unicode-range"))  # subsets must not clash
        for name in files:
            self.assertIsNotNone(finders.find(f"core/fonts/{name}"), name)

    def test_built_stylesheet_has_the_site_styles(self):
        with open(finders.find("core/css/tailwind.css"), encoding="utf-8") as fh:
            css = fh.read()
        for needle in (".bg-depot-teal", ".nav-link", ".dropdown-panel", "[x-cloak]", ".font-display",
                       ".text-depot-moss", ".sm\\:grid-cols-4", ".lg\\:flex", ".divide-y"):
            self.assertIn(needle, css)


class LoggingTests(TestCase):
    def test_crashing_pages_are_logged_with_a_traceback(self):
        self.assertIn("console", settings.LOGGING["handlers"])
        self.assertIn("console", settings.LOGGING["loggers"]["django.request"]["handlers"])
        logger = logging.getLogger("django.request")
        self.assertTrue(logger.handlers or logger.parent.handlers)
