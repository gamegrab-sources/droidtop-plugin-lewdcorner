"""LewdCorner for droidtop: an unofficial gamegrab-sources plugin, not part of droidtop and not
affiliated with LewdCorner.

LewdCorner is a XenForo forum like F95zone, so this plugin works like the F95zone plugin
(gamegrab-sources/droidtop-plugin-f95), in Python and with the forum itself as the only
source (there is no F95Checker-style index for it):
- `library.sources` (A2), Get games: searches thread titles in the Games forum; a thread's
  page shows its version, developer, prefixes and the download links of its first post.
  A link opens in droidtop's web view with the person's LewdCorner session; the download
  the file host starts runs in droidtop's Downloads into the game folder, with an engine
  hint from the thread's prefix.
- `library.updates` (A6): a game linked to its thread is checked for a newer version from
  the thread's title.
- `library.metadata` (A3): the scrape's text for a game: a game linked to its thread is that
  thread; an unlinked one is searched by its title and its folder's name, exact names only, and
  the thread it matched is named back so droidtop links the game to it.
- `ui.facets` (droidtop plugin-api 1.10), target `item.page`: a linked thread's update page, as
  droidtop's bundles (its metadata, the first post, its banner, the first post's download links,
  which droidtop opens itself with the person's session, and the thread).
- The LewdCorner account is droidtop's own account row (web.session G3); the plugin draws none.

The site sits behind a Cloudflare check, so every request goes with the person's web
session (`web.session fetch`), which carries what droidtop's web view got when the person
signed in. It runs contained (5.3) and draws nothing itself.
"""
import json
import re
import time
from urllib.parse import quote_plus, urlparse

import gamegrab as gg  # embedded by build.sh

DOMAIN = "lewdcorner.com"
BASE = "https://lewdcorner.com"
LOGIN_URL = BASE + "/login/"
# XenForo's signed-in cookie (LewdCorner's cookie prefix is xf_).
SIGNED_IN_COOKIE = "xf_user"
# The Games forum (node 6) and its child forums.
GAMES_NODE = 6
SOURCE_KEY = "lewdcorner"

STATE = "state.json"
SEARCH_CACHE_S = 30 * 60
THREAD_CACHE_S = 30 * 60
# The scrape keeps a search and a thread's metadata a week: a library re-scraped would otherwise ask the forum for every
# game again (droidtop docs/SPEC.md 7h, "Fewer requests"). Get games, game pages and update checks keep their own times.
SCRAPE_CACHE_S = 7 * 24 * 60 * 60
CHECK_BUDGET_S = 90

plugin = gg.Plugin("LewdCorner")


# droidtop draws a browser check in its own words and offers Open the site (docs/plugin-api.md 1.3); this sentence is
# only what its notice keeps behind Info.
CHECKED = "LewdCorner showed a browser check instead of its pages."

# What a Cloudflare or JavaScript check page carries instead of the forum (seen on the rig, build 1715:
# "JavaScript is disabled ..." where the search page should be), at any status.
_CHALLENGE = re.compile(
    r"(?i)<title>\s*(?:Just a moment|Attention Required)|cf-chl|cf_chl_opt|challenge-platform|/cdn-cgi/challenge"
    r"|JavaScript is disabled|Enable JavaScript and cookies|Checking (?:if the site connection is secure|your browser)"
)


class Blocked(gg.HostError):
    """Cloudflare (or another browser check) answered instead of the forum."""

    def __init__(self):
        super().__init__("BROWSER_CHECK_REQUIRED", CHECKED)

    def reply(self):
        return gg.error(self.code, self.message)


def is_challenge(status, body):
    """A browser-check page, not the forum: its markers, or (as every XenForo page names its
    template on the <html> element) no `data-template` on an answer that is not an error page."""
    # Every XenForo page carries "JavaScript is disabled" in a <noscript> notice, so that text counts only
    # outside <noscript>; a check page that has nothing else is still caught by the data-template test below.
    if _CHALLENGE.search(re.sub(r"(?is)<noscript\b.*?</noscript>", "", body or "")):
        return True
    return status in (200, 403, 503) and 'data-template="' not in (body or "")


def fetch(url):
    """One page of the forum with the person's session; Blocked when a browser check answers."""
    answer = gg.http(url, session=True)
    if is_challenge(answer.status, answer.body):
        raise Blocked()
    return answer


def thread_url(tid):
    return "%s/threads/%d/" % (BASE, tid)


def search_url(query):
    q = quote_plus(query)
    return (
        BASE
        + "/search/?q=%s&t=post&c%%5Btitle_only%%5D=1&c%%5Bnodes%%5D%%5B0%%5D=%d&c%%5Bchild_nodes%%5D=1&o=relevance" % (q, GAMES_NODE)
    )


def latest_url():
    return "%s/forums/games.%d/" % (BASE, GAMES_NODE)


def site_message(page):
    """XenForo's own error text on a page (search flood control, members only, ...), skipping the
    "JavaScript is disabled" notice every page carries in <noscript>. For deciding what happened only:
    the site's own words never reach the screen (plain_failure says it instead)."""
    page = re.sub(r"(?is)<noscript\b.*?</noscript>", "", page or "")
    m = re.search(r'(?is)<div class="blockMessage[^"]*"[^>]*>(.*?)</div>', page)
    return gg.one_line(m.group(1)) if m else None


def plain_failure(page, status):
    """What went wrong, in plain words, from a forum page that is not the answer."""
    said = (site_message(page) or "").lower()
    if re.search(r"wait|flood|too many|seconds", said):
        return "LewdCorner asks to wait a moment between searches. Try again shortly."
    if re.search(r"permission|members|log in|logged in|register", said):
        return "LewdCorner shows this to members only. Sign in first."
    if status and not 200 <= status < 300:
        return gg.http_error("LewdCorner", status)
    return "LewdCorner could not search right now. Try again later."


def search(query):
    url = search_url(query) if gg.words(query) else latest_url()

    def produce():
        answer = fetch(url)
        if not answer.ok:
            raise gg.HostError("FAILED", plain_failure(answer.body, answer.status))
        rows = gg.thread_list(answer.body, DOMAIN)
        if not rows:
            message = site_message(answer.body)
            if message and not re.search(r"(?i)no results", message):
                raise gg.HostError("FAILED", plain_failure(answer.body, answer.status))
        return rows

    return gg.cached("search-" + url, SEARCH_CACHE_S, produce)


def thread(tid):
    """A thread page, parsed: None when the thread is gone."""
    answer = fetch(thread_url(tid))
    if answer.status in (404, 410):
        return None
    if answer.status == 403:
        raise gg.HostError("FAILED", "LewdCorner shows that thread to some members only.")
    if not answer.ok:
        raise gg.HostError("FAILED", gg.http_error("LewdCorner", answer.status))
    t = gg.thread_page(answer.body, DOMAIN)
    t["id"] = tid
    t["links"] = download_links(t["first_post"])
    t["hidden"] = bool(re.search(r"(?i)must be (registered|logged)[^<]{0,40}(link|see|download)", t["first_post"]))
    return t


def download_links(post):
    """The first post's links that leave the forum: (link, label), in order, each once."""
    out = []
    seen = set()
    for href, text in gg.links(post, BASE + "/"):
        host = (urlparse(href).hostname or "").lower()
        if not href.startswith("https://") or not host or host == DOMAIN or host.endswith("." + DOMAIN):
            continue
        if re.search(r"(?i)\.(png|jpe?g|gif|webp)(\?|$)", href) or href in seen:
            continue
        seen.add(href)
        out.append((href, text or host))
    return out


def result_row(t):
    return {
        "id": str(t["id"]),
        "title": t["name"] or t["title"],
        "subtitle": t.get("developer"),
        "columns": [c for c in (t.get("version"),) if c],
        "badges": t.get("labels") or [],
        "ref": {"id": str(t["id"])},
    }


# ------------------------------------------------------------------ library.sources (A2)


@plugin.on("library.sources", "form")
def _form(args):
    return gg.ok(
        gg.view(
            "Search LewdCorner",
            [gg.text("query", "Search", "", subtitle="Game titles. Leave it empty for the latest updates.")],
        )
    )


@plugin.on("library.sources", "search")
def _search(args):
    values = args.get("values") or {}
    query = (args.get("query") or values.get("query") or "").strip()[:100]
    try:
        rows = search(query)
    except Blocked as e:
        # No result row about it: droidtop says so under the source's name, with Open the site (Droidtop/tracker#592).
        return e.reply()
    return gg.ok({"results": [result_row(t) for t in rows[:100]]})


@plugin.job("library.sources", "signIn")
def _sources_sign_in(args, report):
    ok = gg.sign_in(LOGIN_URL, SIGNED_IN_COOKIE)
    return gg.done("Signed in to LewdCorner: search again" if ok else "Not signed in")


def _tid(args):
    try:
        tid = int(str((args.get("ref") or {}).get("id") or ""))
    except ValueError:
        return None
    return tid if tid > 0 else None


@plugin.on("library.sources", "detail")
def _detail(args):
    if (args.get("ref") or {}).get("signIn"):
        # The sign-in row an older version listed, opened from a page droidtop still shows.
        return Blocked().reply()
    tid = _tid(args)
    if tid is None:
        return gg.error("INVALID_ARGS", "Missing thread")
    try:
        t = thread(tid)
    except Blocked as e:
        return e.reply()
    if t is None:
        return gg.error("NOT_FOUND", "That thread is gone")
    return gg.ok(detail_view(t, gg.signed_in()))


DOWNLOAD_NOTE = "Opens the file host's page. The download it starts goes to Downloads."


def detail_view(t, signed_in):
    about = gg.strip_tags(t.get("first_post") or "")
    items = [
        gg.info("version", "Version", t.get("version")) if t.get("version") else None,
        gg.info("developer", "Developer", t.get("developer")) if t.get("developer") else None,
        gg.info("labels", "Tags", ", ".join(t["labels"])) if t.get("labels") else None,
        gg.info("about", "About", subtitle=gg.cut(about, 500)) if about else None,
        gg.button("page", "Open the thread", gg.job("handoff", "Open the thread", {"uri": thread_url(t["id"]), "title": t.get("name") or ""}), subtitle="In your browser"),
    ]
    sections = [gg.section("main", items)]
    links = t.get("links") or []
    rows = []
    if not signed_in:
        rows.append(gg.info("signin", "Sign in to download", subtitle="LewdCorner shows download links to members."))
        rows.append(gg.button("signin-button", "Sign in to LewdCorner", gg.job("signIn", "Sign in to LewdCorner")))
    if links:
        for i, (href, label) in enumerate(links[:40]):
            host = urlparse(href).hostname or href
            rows.append(
                gg.button(
                    "dl-%d" % i,
                    gg.cut("%s (%s)" % (label, host) if label != host else host, 200),
                    gg.job("acquire", "Download %s" % (t.get("name") or ""), {"ref": {"id": str(t["id"])}, "link": href}),
                    subtitle=DOWNLOAD_NOTE if i == 0 else None,
                )
            )
    elif signed_in:
        rows.append(gg.info("none", "No download links found", subtitle="Open the thread to see what it offers."))
    sections.append(gg.section("downloads", rows, "Download"))
    return gg.view(gg.cut(t.get("name") or t.get("title") or "Thread", 200), [], sections=sections)


@plugin.job("library.sources", "acquire")
def _acquire(args, report):
    tid = _tid(args)
    link = str(args.get("link") or "")
    if tid is None or not link.startswith("https://"):
        return gg.failed("Choose a download link first")
    if not gg.signed_in():
        return gg.failed("Sign in to LewdCorner first.")
    try:
        t = thread(tid)
    except Blocked as e:
        return gg.failed(str(e))
    if t is None:
        return gg.failed("That thread is gone")
    if link not in [h for h, _ in t["links"]]:
        return gg.failed("That link is no longer in the thread; open it again")
    report(-1, "Opening %s" % (urlparse(link).hostname or "the link"))
    download = gg.open_in_session(link)
    if download is None:
        return gg.failed("No download was started on that page")
    # droidtop pins the placed game to this engine's player (plugin-api 1.6, engine hint).
    return gg.done("Downloading %s" % (t.get("name") or "the game"), download=download, engine=gg.engine_of(t.get("labels")))


@plugin.job("library.sources", "handoff")
def _handoff(args, report):
    uri = str(args.get("uri") or "")
    if not uri.startswith(BASE + "/"):
        return gg.failed("Missing link")
    title = str(args.get("title") or "LewdCorner")
    return gg.handoff_result(uri, title, "Opened in your browser", "Open it in your browser.")


# ------------------------------------------------------------------ library.updates (A6)


@plugin.on("library.updates", "resolve")
def _resolve(args):
    tid = gg.thread_id(args.get("text"), DOMAIN)
    return gg.ok({"found": {"id": str(tid), "url": thread_url(tid)}} if tid else {})


@plugin.on("library.updates", "match")
def _match(args):
    title = str(args.get("title") or "")
    if not gg.words(title):
        return gg.ok({"candidates": []})
    try:
        rows = search(title)
    except Blocked:
        return gg.ok({"candidates": []})
    key = gg.name_key(title)
    rows = sorted(rows, key=lambda t: gg.name_key(t["name"]) != key)
    out = []
    for t in rows[:20]:
        c = {"id": str(t["id"]), "title": t["name"], "url": thread_url(t["id"])}
        if t.get("version"):
            c["version"] = t["version"]
        note = ", ".join(x for x in (("by " + t["developer"]) if t.get("developer") else "", ", ".join(t.get("labels") or [])) if x)
        if note:
            c["note"] = note
        out.append(c)
    return gg.ok({"candidates": out})


@plugin.on("library.updates", "check")
def _check(args):
    ids = []
    for raw in (args.get("ids") or [])[:50]:
        try:
            ids.append(int(str(raw)))
        except ValueError:
            continue
    state = gg.read_json(STATE, {}) or {}
    seen = state.setdefault("versions", {})
    answers = []
    news = []
    started = time.monotonic()
    for tid in ids:
        if time.monotonic() - started > CHECK_BUDGET_S:
            break  # the rest keep their last answer until the next round
        try:
            t = thread(tid)
        except Blocked:
            break  # not signed in, or the check came back: nothing more this round
        if t is None:
            answers.append({"id": str(tid), "gone": True})
            continue
        version = t.get("version")
        before = seen.get(str(tid))
        if version and before and before != version:
            news.append("%s: %s" % (t.get("name") or "Thread %d" % tid, version))
        if version:
            seen[str(tid)] = version
        answer = {"id": str(tid), "url": thread_url(tid)}
        if version:
            answer["version"] = version
        answers.append(answer)
    gg.write_json(STATE, state)
    if news:
        gg.notify("New version on LewdCorner" if len(news) == 1 else "%d new versions on LewdCorner" % len(news), "\n".join(news[:8]))
    return gg.ok({"answers": answers})


# ------------------------------------------------------------------ library.metadata (A3)

_PLATFORM = re.compile(r"(?i)[-_ .](pc|win|windows|linux|mac|osx|android|market)$")
# A version is marked (v2, Ep3) or dotted (0.9.5): a bare trailing number may be the name's own ("Fallout 4").
_VERSION = re.compile(r"(?i)[-_ .]+((v|ver|version|ep|episode|ch|chapter)[ ._-]?\d+([._]\d+)*|\d+([._]\d+)+)[a-z]?$")


def folder_title(folder):
    """A game folder's name without what a release adds to it, a version and a platform:
    "Sample_Game-0.5-pc" searches as "Sample Game" (the same rule as the F95zone plugin)."""
    name = (folder or "").strip()
    for _ in range(4):
        before = name
        name = _VERSION.sub("", _PLATFORM.sub("", name, count=1), count=1).strip()
        if name == before:
            break
    return re.sub(r"[_.]+", " ", name).strip()


def first_picture(post):
    """The first picture of the thread's first post on the forum itself (its banner, by the forum's habit), for
    droidtop to fetch as the game's cover; None when the post has none there. A picture on another host is left out:
    droidtop fetches a plugin's picture only from the plugin's own sites."""
    for m in re.finditer(r'(?is)<img\b[^>]*?\b(?:data-src|src)\s*=\s*["\']([^"\']+)["\']', post or ""):
        src = gg.unescape(m.group(1))
        if src.startswith("/"):
            src = BASE + src
        host = (urlparse(src).hostname or "").lower()
        if src.startswith("https://") and (host == DOMAIN or host.endswith("." + DOMAIN)) and not re.search(r"(?i)/(styles|smilies|data/avatars)/", src):
            return src
    return None


# ------------------------------------------------------------------ ui.facets (droidtop plugin-api 1.10)

ITEM_PAGE = "item.page"
ITEM_TTL_S = 86400


@plugin.on("ui.facets", "get")
def _facets(args):
    """The update page of a linked thread (target item.page): what droidtop asks in place of a `record`."""
    if args.get("target") != ITEM_PAGE:
        return gg.ok({"facets": []})
    subject = args.get("subject") or {}
    tid = gg.thread_id(str(subject.get("id") or ""), DOMAIN)
    if tid is None:
        return gg.error("INVALID_ARGS", "Missing thread")
    try:
        t = thread(tid)
    except Blocked as e:
        return e.reply()
    if t is None:
        return gg.error("NOT_FOUND", "That thread is gone")
    return gg.ok({"items": [item_page(t)]})


def item_page(t):
    """The thread as one item of droidtop's item page: its metadata, the first post, its banner, the download
    links of its first post (pages droidtop opens itself with the person's session) and the thread."""
    tid = str(t["id"])
    about = gg.strip_tags(t.get("first_post") or "")
    meta = {"id": "meta", "kind": "metadata", "v": 1, "title": gg.cut(t.get("name") or t.get("title") or "Thread", 200)}
    if t.get("version"):
        meta["version"] = t["version"]
    if t.get("developer"):
        meta["developer"] = t["developer"]
    if t.get("labels"):
        meta["tags"] = t["labels"]
    facets = [meta]
    if about:
        facets.append({"id": "about", "kind": "description", "v": 1, "overview": gg.cut(about, 4000)})
    cover = first_picture(t.get("first_post") or "")
    if cover:
        facets.append({"id": "cover", "kind": "image", "v": 1, "role": "cover", "url": cover, "alt": meta["title"]})
    entries = []
    for href, label in (t.get("links") or [])[:40]:
        host = urlparse(href).hostname or href
        entries.append({"section": "Downloads", "host": host, "label": gg.cut(label, 200), "url": href, "kind": "page"})
    if entries:
        facets.append({"id": "dl", "kind": "download", "v": 1, "entries": entries})
    facets.append({"id": "links", "kind": "links", "v": 1, "entries": [{"kind": "source", "label": "LewdCorner thread", "url": thread_url(t["id"])}]})
    return {"source": SOURCE_KEY, "id": tid, "ttl": ITEM_TTL_S, "facets": facets}


@plugin.on("library.metadata", "match")
def _metadata_match(args):
    """droidtop's scrape asks which thread a game is (droidtop docs/SPEC.md 7h, "A source's own
    match"). A game linked to its thread is that thread. Otherwise the title and the folder's name
    are searched and only exact names count: one thread is the game; several with that name tie,
    and droidtop asks the person to pick."""
    linked = str((args.get("sourceLinks") or {}).get(SOURCE_KEY) or "")
    if linked.isdigit():
        return gg.ok({"candidates": [{"ids": {"thread": linked}, "confidence": 1.0}]})
    folder = str((args.get("folder") or {}).get("name") or args.get("fileName") or "")
    queries = {}
    for query in (str(args.get("title") or ""), folder_title(folder)):
        key = gg.name_key(query)
        if key and gg.words(query):
            queries.setdefault(key, query)
    found = {}
    for key, query in queries.items():
        try:
            rows = gg.cached("scrape-search-" + key, SCRAPE_CACHE_S, lambda q=query: [{"id": t["id"], "name": t["name"]} for t in search(q)])
        except Blocked:
            # Not signed in, or the check came back: no answer is better than a guess.
            return gg.ok({"candidates": []})
        for t in rows:
            if gg.name_key(t["name"]) == key:
                found.setdefault(t["id"], t["name"])
    confidence = 0.95 if len(found) == 1 else 0.6
    return gg.ok({"candidates": [{"ids": {"thread": str(tid)}, "confidence": confidence, "title": name} for tid, name in found.items()]})


@plugin.on("library.metadata", "fetch")
def _metadata_fetch(args):
    """The thread's text for the game, and the thread itself as `sourceLinks`, so droidtop links
    the game to it: the next scrape and the update checks find it without a search."""
    try:
        tid = int(str((args.get("ids") or {}).get("thread") or ""))
    except ValueError:
        return gg.error("INVALID_ARGS", "Missing thread")
    try:
        fields = gg.cached("scrape-thread-%d" % tid, SCRAPE_CACHE_S, lambda: _metadata_fields(tid))
    except Blocked as e:
        return e.reply()
    if fields is None:
        return gg.error("NOT_FOUND", "That thread is gone")
    return gg.ok(fields)


def _metadata_fields(tid):
    """What library.metadata fetch answers for the thread, or None when it is gone."""
    t = thread(tid)
    if t is None:
        return None
    fields = {"sourceLinks": {SOURCE_KEY: str(tid)}}
    cover = first_picture(t.get("first_post") or "")
    if cover:
        fields["cover"] = cover
    about = gg.strip_tags(t.get("first_post") or "")
    if about:
        fields["description"] = gg.cut(about, 2000)
    if t.get("developer"):
        fields["developer"] = t["developer"]
    # The engine prefix (Ren'Py, Unity, ...) as the genre line, as the F95zone plugin gives it.
    engine = next((label for label in t.get("labels") or [] if gg.engine_of([label])), None)
    if engine:
        fields["genre"] = engine
    return fields


handle, start_job, cancel_job = plugin.entry_points()
