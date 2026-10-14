"""Tests for the LewdCorner plugin (python3 test_plugin.py, after build.sh: it also loads the
built plugin.py with gamegrab embedded). The pages below are small hand-written samples in
XenForo's markup, not copies of the site's pages."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "common"), os.path.join(HERE, "src")]

import gamegrab as gg  # noqa: E402
import plugin  # noqa: E402
from testing import FakeHost, envelope, install  # noqa: E402

SEARCH = """<html data-template="search_results"><body><ol class="block-body">
<li class="block-row block-row--separated js-inlineModContainer" data-author="a"><div class="contentRow"><div class="contentRow-main">
<h3 class="contentRow-title"><a href="/threads/sample-game-v0-5-sample-dev.18978/"><span class="label label--blue" dir="auto">Ren'Py</span> Sample Game [v0.5] [Sample Dev]</a></h3>
</div></div></li>
<li class="block-row block-row--separated js-inlineModContainer" data-author="b"><div class="contentRow"><div class="contentRow-main">
<h3 class="contentRow-title"><a href="/threads/other-game.2201/">Other Game [Ep. 2] [Studio]</a></h3>
</div></div></li></ol></body></html>"""


def thread_page(version):
    return """<html data-csrf="1,abc" data-template="thread_view"><head><title>Sample Game [%s] [Sample Dev] | LewdCorner</title></head><body>
<h1 class="p-title-value"><span class="label label--blue" dir="auto">Ren'Py</span><span class="label-append">&nbsp;</span>Sample Game [%s] [Sample Dev]</h1>
<article class="message message--post js-post" data-content="post-1"><div class="message-content">
<div class="bbWrapper">A story.<br /><img src="https://lewdcorner.com/attachments/cover.png" />
<b>DOWNLOAD</b><br />Win/Linux: <a href="https://files.example/abc" class="link link--external">FILES</a> -
<a href="https://other.example/u/xyz" class="link link--external">OTHER</a><br />
<a href="https://lewdcorner.com/threads/other.5/" class="link link--internal">other thread</a></div>
<div class="js-selectToQuoteEnd">&nbsp;</div></div></article></body></html>""" % (version, version)


SEARCH_URL = plugin.search_url("sample game")


def call(point, op, args=None):
    return json.loads(plugin.handle(envelope(point, op, args)))


def job(point, op, args=None):
    return json.loads(plugin.start_job("j", json.loads(envelope(point, op, args)), lambda p, s: None))


class LewdCorner(unittest.TestCase):
    def setUp(self):
        self.host = install(gg, FakeHost({SEARCH_URL: SEARCH, plugin.thread_url(18978): thread_page("v0.5")}, signed_in=True))

    def test_search(self):
        rows = call("library.sources", "search", {"query": "sample game"})["data"]["results"]
        self.assertEqual([(r["id"], r["title"], r["subtitle"], r["columns"], r["badges"]) for r in rows], [("18978", "Sample Game", "Sample Dev", ["v0.5"], ["Ren'Py"]), ("2201", "Other Game", "Studio", ["Ep. 2"], [])])
        self.assertTrue(all(a == "web.session" for a, o, _ in self.host.calls if o in ("fetch", "http")))

    def assert_sign_in_offered(self):
        rows = call("library.sources", "search", {"query": "sample game"})["data"]["results"]
        self.assertEqual([r["id"] for r in rows], ["signin"])
        self.assertEqual(rows[0]["subtitle"], "Sign in to LewdCorner to search it.")
        page = call("library.sources", "detail", {"ref": rows[0]["ref"]})["data"]
        items = page["sections"][0]["items"]
        self.assertEqual(items[0]["title"], "Sign in to LewdCorner to search it.")
        self.assertEqual(items[1]["action"]["op"], "signIn")
        self.assertEqual(job("library.sources", "signIn")["values"]["message"], "Signed in to LewdCorner: search again")
        self.assertEqual(self.host.calls[-1], ("web.session", "sign_in", {"url": "https://lewdcorner.com/login/", "doneCookie": "xf_user"}))

    def test_cloudflare_offers_sign_in(self):
        self.host.signed_in = False  # the fake answers 403 "Just a moment..."
        self.assert_sign_in_offered()

    def test_javascript_check_page_offers_sign_in(self):
        # What the rig got (BlueStacks, build 1715): a page saying JavaScript is disabled, not the forum.
        self.host.pages[SEARCH_URL] = (200, "<html><body><noscript>JavaScript is disabled. In order to continue, enable JavaScript.</noscript></body></html>")
        self.assert_sign_in_offered()
        self.host.pages[SEARCH_URL] = (200, "<html><body>Something that is not the forum</body></html>")
        self.assertEqual(call("library.sources", "search", {"query": "sample game"})["data"]["results"][0]["id"], "signin")

    def test_the_noscript_notice_on_every_forum_page_is_not_a_check(self):
        notice = '<noscript class="js-jsWarning"><div class="blockMessage">JavaScript is disabled. For a better experience, please enable JavaScript in your browser before proceeding.</div></noscript>'
        self.host.pages[SEARCH_URL] = (200, SEARCH.replace("<body>", "<body>" + notice))
        rows = call("library.sources", "search", {"query": "sample game"})["data"]["results"]
        self.assertEqual([r["id"] for r in rows], ["18978", "2201"])

    def test_site_text_never_reaches_the_screen(self):
        noscript = '<noscript><div class="blockMessage">JavaScript is disabled. For a better experience, please enable JavaScript.</div></noscript>'
        flood = '<html data-template="error">%s<div class="blockMessage">You must wait at least 30 seconds before performing this action.</div></html>' % noscript
        self.host.pages[SEARCH_URL] = (200, flood)
        reply = call("library.sources", "search", {"query": "sample game"})
        self.assertEqual(reply["error"]["message"], "LewdCorner asks to wait a moment between searches. Try again shortly.")
        self.assertEqual(plugin.plain_failure("<html>%s</html>" % noscript, 503), "LewdCorner is not answering right now. Try again later.")

    def test_form_offers_sign_in_until_signed_in(self):
        self.assertEqual(len(call("library.sources", "form")["data"]["sections"][0]["items"]), 1)
        self.host.signed_in = False
        items = call("library.sources", "form")["data"]["sections"][0]["items"]
        self.assertEqual(items[-1]["action"]["op"], "signIn")

    def test_detail_lists_the_first_posts_links(self):
        page = call("library.sources", "detail", {"ref": {"id": "18978"}})["data"]
        dl = [s for s in page["sections"] if s["id"] == "downloads"][0]["items"]
        self.assertEqual([n["action"]["args"]["link"] for n in dl], ["https://files.example/abc", "https://other.example/u/xyz"])

    def test_acquire_through_the_web_view_with_engine_hint(self):
        self.host.captured = {"url": "https://cdn.example/game.zip", "fileName": "game.zip", "session": "w-00000000-0000-0000-0000-000000000000"}
        result = job("library.sources", "acquire", {"ref": {"id": "18978"}, "link": "https://files.example/abc"})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["values"]["engine"], "renpy")
        self.assertEqual(json.loads(result["values"]["download"])["fileName"], "game.zip")
        self.assertFalse(job("library.sources", "acquire", {"ref": {"id": "18978"}, "link": "https://evil.example/"})["ok"])

    def test_updates(self):
        self.assertEqual(call("library.updates", "resolve", {"text": "https://lewdcorner.com/threads/sample-game.18978/"})["data"]["found"]["id"], "18978")
        answers = call("library.updates", "check", {"ids": ["18978", "5"]})["data"]["answers"]
        self.assertEqual(answers, [{"id": "18978", "url": "https://lewdcorner.com/threads/18978/", "version": "v0.5"}, {"id": "5", "gone": True}])
        self.host.pages[plugin.thread_url(18978)] = thread_page("v0.6")
        call("library.updates", "check", {"ids": ["18978"]})
        self.assertEqual(len(self.host.notes), 1)
        self.assertIn("v0.6", self.host.notes[0]["text"])
        c = call("library.updates", "match", {"title": "sample game"})["data"]["candidates"]
        self.assertEqual(c[0]["id"], "18978")

    def test_sign_in_and_out(self):
        self.host.signed_in = False
        view = call("ui.settings", "view")["data"]
        self.assertEqual(view["sections"][0]["items"][1]["action"]["op"], "signIn")
        self.assertEqual(job("ui.settings", "signIn")["values"]["message"], "Signed in to LewdCorner")
        self.assertEqual(self.host.calls[-1][2], {"url": "https://lewdcorner.com/login/", "doneCookie": "xf_user"})
        self.assertTrue(call("ui.settings", "signOut")["ok"])
        self.assertFalse(self.host.signed_in)

    def test_open_the_thread_in_the_browser(self):
        uri = plugin.thread_url(18978)
        self.assertEqual(job("library.sources", "handoff", {"uri": uri, "title": "x"})["values"]["message"], "Opened in your browser")
        self.assertEqual(self.host.calls[-1], ("link", "open", {"uri": uri, "title": "x"}))
        self.assertFalse(job("library.sources", "handoff", {"uri": "https://elsewhere.example/"})["ok"])
        self.host.handoff = "denied"
        page = json.loads(job("library.sources", "handoff", {"uri": uri})["values"]["view"])
        self.assertIn("Open links in other apps", page["sections"][0]["items"][0]["subtitle"])


class Built(unittest.TestCase):
    def test_built_plugin_loads(self):
        built = os.path.join(HERE, "build", "plugin.py")
        if not os.path.exists(built):
            self.skipTest("run build.sh first")
        with open(built, encoding="utf-8") as f:
            source = f.read()
        scope = {"__name__": "built"}
        exec(compile(source, "plugin.py", "exec"), scope)
        install(scope["gg"], FakeHost())
        self.assertTrue(json.loads(scope["handle"](envelope("ui.settings", "view")))["ok"])


if __name__ == "__main__":
    unittest.main()
