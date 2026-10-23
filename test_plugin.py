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

    def assert_browser_check(self):
        reply = call("library.sources", "search", {"query": "sample game"})
        self.assertEqual(reply["error"]["code"], "BROWSER_CHECK_REQUIRED", reply)
        self.assertNotIn("data", reply, "no made-up result row")
        page = call("library.sources", "detail", {"ref": {"id": "18978"}})
        self.assertEqual(page["error"]["code"], "BROWSER_CHECK_REQUIRED")

    def test_cloudflare_is_a_browser_check(self):
        self.host.signed_in = False  # the fake answers 403 "Just a moment..."
        self.assert_browser_check()
        self.assertEqual(call("library.sources", "detail", {"ref": {"signIn": True}})["error"]["code"], "BROWSER_CHECK_REQUIRED")
        self.assertEqual(call("library.metadata", "fetch", {"ids": {"thread": "18978"}})["error"]["code"], "BROWSER_CHECK_REQUIRED")

    def test_javascript_check_page_is_a_browser_check(self):
        # What the rig got (BlueStacks, build 1715): a page saying JavaScript is disabled, not the forum.
        check = (200, "<html><body><noscript>JavaScript is disabled. In order to continue, enable JavaScript.</noscript></body></html>")
        self.host.pages[SEARCH_URL] = check
        self.host.pages[plugin.thread_url(18978)] = check
        self.assert_browser_check()
        self.host.pages[SEARCH_URL] = (200, "<html><body>Something that is not the forum</body></html>")
        self.assertEqual(call("library.sources", "search", {"query": "sample game"})["error"]["code"], "BROWSER_CHECK_REQUIRED")

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

    def test_the_form_is_only_the_search(self):
        self.host.signed_in = False
        items = call("library.sources", "form")["data"]["sections"][0]["items"]
        self.assertEqual([n["id"] for n in items], ["query"])

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

    def test_droidtop_draws_the_account(self):
        # Droidtop/tracker#593: the account row is droidtop's, from web.session's signIn; the plugin has no settings of its own.
        self.assertEqual(call("ui.settings", "view")["error"]["code"], "UNSUPPORTED")
        with open(os.path.join(HERE, "manifest.template.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        session = [p for p in manifest["permissions"] if p["id"] == "web.session"][0]
        self.assertEqual((session["signIn"], session["doneCookie"]), (plugin.LOGIN_URL, plugin.SIGNED_IN_COOKIE))
        self.assertNotIn("ui.settings", [p["point"] for p in manifest["provides"]])

    def test_the_update_page_is_the_threads_item_page_bundles(self):
        reply = call("ui.facets", "get", {"target": "item.page", "subject": {"type": "item", "source": "lewdcorner", "id": "18978"}})
        item = reply["data"]["items"][0]
        self.assertEqual((item["source"], item["id"]), ("lewdcorner", "18978"))
        facets = {f["kind"]: f for f in item["facets"]}
        self.assertEqual(facets["metadata"]["title"], "Sample Game")
        self.assertEqual(facets["metadata"]["version"], "v0.5")
        self.assertEqual(facets["image"]["url"], "https://lewdcorner.com/attachments/cover.png")
        self.assertEqual([e["url"] for e in facets["download"]["entries"]], ["https://files.example/abc", "https://other.example/u/xyz"])
        self.assertEqual(facets["links"]["entries"][0]["url"], "https://lewdcorner.com/threads/18978/")
        self.assertEqual(call("ui.facets", "get", {"target": "quickmenu"})["data"]["facets"], [])
        gone = call("ui.facets", "get", {"target": "item.page", "subject": {"type": "item", "source": "lewdcorner", "id": "5"}})
        self.assertEqual(gone["error"]["code"], "NOT_FOUND")
        with open(os.path.join(HERE, "manifest.template.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        facets_entry = [p for p in manifest["provides"] if p["point"] == "ui.facets"][0]
        self.assertEqual(facets_entry["targets"], ["item.page"])

    def test_each_link_names_the_systems_of_its_heading(self):
        self.assertEqual(plugin.systems_of("Win/Linux"), ["windows", "linux"])
        self.assertEqual(plugin.systems_of("Android (APK)"), ["android"])
        self.assertEqual(plugin.systems_of("DOWNLOAD"), [])
        post = ('<b>Win/Linux</b><br /><a href="https://a.example/1">MEGA</a> - <a href="https://b.example/1">GOFILE</a><br />'
                '<b>Mac</b>: <a href="https://a.example/2">MEGA</a><br />'
                'Android: <a href="https://a.example/3">MEGA</a><br />'
                '<a href="https://c.example/4">GOFILE</a><br />'
                'Walkthrough: <a href="https://c.example/walk">PDF</a>')
        self.assertEqual(plugin.link_headings(post), {
            "https://a.example/1": "Win/Linux", "https://b.example/1": "Win/Linux",
            "https://a.example/2": "Mac", "https://a.example/3": "Android", "https://c.example/4": "Android",
            "https://c.example/walk": "Walkthrough",
        })
        # An extra on a line of its own heads the links below it, and says what they are.
        extras = plugin.link_headings('<b>Save file</b><br /><a href="https://d.example/s">MEGA</a><br />A note.<br /><a href="https://d.example/n">x</a>')
        self.assertEqual(extras, {"https://d.example/s": "Save file"})
        item = call("ui.facets", "get", {"target": "item.page", "subject": {"type": "item", "source": "lewdcorner", "id": "18978"}})["data"]["items"][0]
        entries = [f for f in item["facets"] if f["kind"] == "download"][0]["entries"]
        self.assertEqual([(e["section"], e["systems"]) for e in entries], [("Win/Linux", ["windows", "linux"])] * 2)

    def test_a_thread_offers_sign_in_to_see_its_links(self):
        t = plugin.thread(18978)
        page = plugin.detail_view(t, signed_in=False)
        dl = [s for s in page["sections"] if s["id"] == "downloads"][0]["items"]
        self.assertEqual(dl[1]["action"]["op"], "signIn")
        self.assertEqual(job("library.sources", "signIn")["values"]["message"], "Signed in to LewdCorner: search again")
        self.assertEqual(self.host.calls[-1], ("web.session", "sign_in", {"url": "https://lewdcorner.com/login/", "doneCookie": "xf_user"}))

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
        self.assertTrue(json.loads(scope["handle"](envelope("library.sources", "form")))["ok"])



class Metadata(unittest.TestCase):
    """library.metadata (droidtop #575): exact names by title and folder, and the thread named back."""

    def setUp(self):
        self.host = install(gg, FakeHost({SEARCH_URL: SEARCH, plugin.thread_url(18978): thread_page("v0.5")}, signed_in=True))

    def test_an_exact_name_by_the_folder_is_the_game_and_its_fetch_links_it(self):
        reply = call("library.metadata", "match", {"title": "sample game", "folder": {"name": "Sample_Game-0.5-pc"}})["data"]
        self.assertEqual(reply["candidates"], [{"ids": {"thread": "18978"}, "confidence": 0.95, "title": "Sample Game"}])
        # The folder's name searches as the same name, so the forum was asked once.
        self.assertEqual(len([c for c in self.host.calls if c[1] == "fetch"]), 1)
        fetched = call("library.metadata", "fetch", {"ids": {"thread": "18978"}})["data"]
        self.assertEqual(fetched["sourceLinks"], {"lewdcorner": "18978"})
        self.assertEqual(fetched["developer"], "Sample Dev")
        self.assertEqual(fetched["genre"], "Ren'Py")
        self.assertTrue(fetched["description"].startswith("A story."))
        self.assertEqual(fetched["cover"], "https://lewdcorner.com/attachments/cover.png")

    def test_a_picture_off_the_forum_or_a_smiley_is_not_the_cover(self):
        self.assertIsNone(plugin.first_picture('<img src="https://imgbox.example/a.png"><img src="/styles/smilies/x.png">'))
        self.assertEqual(plugin.first_picture('<img class="bbImage" data-src="/attachments/b.jpg" src="data:x">'), "https://lewdcorner.com/attachments/b.jpg")

    def test_a_second_scrape_within_the_week_asks_the_forum_nothing(self):
        for _ in range(2):
            call("library.metadata", "match", {"title": "sample game"})
            call("library.metadata", "fetch", {"ids": {"thread": "18978"}})
        self.assertEqual(len([c for c in self.host.calls if c[1] == "fetch"]), 2)

    def test_a_linked_game_is_its_thread_without_a_search(self):
        reply = call("library.metadata", "match", {"title": "Anything", "sourceLinks": {"lewdcorner": "77"}})["data"]
        self.assertEqual(reply["candidates"], [{"ids": {"thread": "77"}, "confidence": 1.0}])
        self.assertEqual([c for c in self.host.calls if c[1] in ("fetch", "http")], [])

    def test_a_near_name_is_not_a_match_and_a_check_page_is_no_answer(self):
        self.host.pages[plugin.search_url("Sample")] = (200, SEARCH)
        self.assertEqual(call("library.metadata", "match", {"title": "Sample"})["data"]["candidates"], [])
        self.host.signed_in = False
        self.assertEqual(call("library.metadata", "match", {"title": "Sample Game"})["data"]["candidates"], [])

    def test_folder_titles(self):
        self.assertEqual(plugin.folder_title("Sample_Game-0.5-pc"), "Sample Game")
        self.assertEqual(plugin.folder_title("Game_Ep3-win"), "Game")
        self.assertEqual(plugin.folder_title("Fallout 4"), "Fallout 4")

if __name__ == "__main__":
    unittest.main()
