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
- `ui.settings`: sign in on LewdCorner's own page in droidtop's web view (web.session G3),
  sign out.

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
CHECK_BUDGET_S = 90

plugin = gg.Plugin("LewdCorner")


CLOUDFLARE = "LewdCorner needs you to sign in once in droidtop's browser view."
CLOUDFLARE_MORE = (
    "Its Cloudflare check lets this plugin's requests through only with the session droidtop's browser view "
    "gets when you sign in there."
)

# What a Cloudflare or JavaScript check page carries instead of the forum (seen on the rig, build 1715:
# "JavaScript is disabled ..." where the search page should be), at any status.
_CHALLENGE = re.compile(
    r"(?i)<title>\s*(?:Just a moment|Attention Required)|cf-chl|cf_chl_opt|challenge-platform|/cdn-cgi/challenge"
    r"|JavaScript is disabled|Enable JavaScript and cookies|Checking (?:if the site connection is secure|your browser)"
)


class Blocked(gg.HostError):
    """Cloudflare (or another browser check) answered instead of the forum."""

    def __init__(self):
        super().__init__("FAILED", CLOUDFLARE + " " + CLOUDFLARE_MORE)


def is_challenge(status, body):
    """A browser-check page, not the forum: its markers, or (as every XenForo page names its
    template on the <html> element) no `data-template` on an answer that is not an error page."""
    if _CHALLENGE.search(body or ""):
        return True
    return status in (200, 403, 503) and 'data-template="' not in (body or "")


def fetch(url):
    """One page of the forum with the person's session; Blocked when a browser check answers."""
    answer = gg.http(url, session=True)
    if is_challenge(answer.status, answer.body):
        raise Blocked()
    return answer


def sign_in_view(why):
    """What Get games shows when the forum cannot be reached without a signed-in session: the
    plain sentence and the Sign in action (a job: droidtop's browser view opens LewdCorner's login)."""
    return gg.view(
        "LewdCorner",
        [
            gg.info("why", CLOUDFLARE, subtitle=why),
            gg.button("signin", "Sign in to LewdCorner", gg.job("signIn", "Sign in to LewdCorner")),
        ],
    )


SIGN_IN_ROW_ID = "signin"


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
    """XenForo's own error text on a page (search flood control, members only, ...)."""
    m = re.search(r'(?is)<div class="blockMessage[^"]*"[^>]*>(.*?)</div>', page or "")
    return gg.one_line(m.group(1)) if m else None


def search(query):
    url = search_url(query) if gg.words(query) else latest_url()

    def produce():
        answer = fetch(url)
        if not answer.ok:
            raise gg.HostError("FAILED", site_message(answer.body) or "LewdCorner answered HTTP %d" % answer.status)
        rows = gg.thread_list(answer.body, DOMAIN)
        if not rows:
            message = site_message(answer.body)
            if message and not re.search(r"(?i)no results", message):
                raise gg.HostError("FAILED", message)
        return rows

    return gg.cached("search-" + url, SEARCH_CACHE_S, produce)


def thread(tid):
    """A thread page, parsed: None when the thread is gone."""
    answer = fetch(thread_url(tid))
    if answer.status in (404, 410):
        return None
    if answer.status == 403:
        raise gg.HostError("FAILED", site_message(answer.body) or "LewdCorner shows that thread only to some members")
    if not answer.ok:
        raise gg.HostError("FAILED", "LewdCorner answered HTTP %d" % answer.status)
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
    signed_in = gg.signed_in()
    return gg.ok(
        gg.view(
            "Search LewdCorner",
            [
                gg.text("query", "Search", ""),
                gg.info("hint", "Thread titles in the Games forum", subtitle="Leave it empty for the latest updated threads."),
                None if signed_in else gg.info("signin-why", CLOUDFLARE, subtitle=CLOUDFLARE_MORE),
                None if signed_in else gg.button("signin", "Sign in to LewdCorner", gg.job("signIn", "Sign in to LewdCorner")),
            ],
        )
    )


def sign_in_row():
    """The one result Get games lists while a browser check stands in the way: opening it shows
    the sentence and the Sign in action."""
    return {
        "id": SIGN_IN_ROW_ID,
        "title": "Sign in to LewdCorner",
        "subtitle": CLOUDFLARE,
        "badges": ["Sign in"],
        "ref": {"signIn": True},
    }


@plugin.on("library.sources", "search")
def _search(args):
    values = args.get("values") or {}
    query = (args.get("query") or values.get("query") or "").strip()[:100]
    try:
        rows = search(query)
    except Blocked:
        return gg.ok({"results": [sign_in_row()]})
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
        return gg.ok(sign_in_view(CLOUDFLARE_MORE))
    tid = _tid(args)
    if tid is None:
        return gg.error("INVALID_ARGS", "Missing thread")
    try:
        t = thread(tid)
    except Blocked:
        return gg.ok(sign_in_view(CLOUDFLARE_MORE))
    if t is None:
        return gg.error("NOT_FOUND", "That thread is gone")
    return gg.ok(detail_view(t, gg.signed_in()))


DOWNLOAD_NOTE = (
    "Opens the link in droidtop's browser view with your LewdCorner session. Go through the "
    "file host's page yourself; the download it starts runs in droidtop's Downloads into this game folder."
)


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
        rows.append(gg.info("signin", "Sign in to download", subtitle="LewdCorner shows download links to members. Sign in on this plugin's Settings page."))
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
        rows.append(gg.info("none", "No download links in the first post", subtitle="Open the thread to see where it keeps them."))
    sections.append(gg.section("downloads", rows, "Download"))
    return gg.view(gg.cut(t.get("name") or t.get("title") or "Thread", 200), [], sections=sections)


@plugin.job("library.sources", "acquire")
def _acquire(args, report):
    tid = _tid(args)
    link = str(args.get("link") or "")
    if tid is None or not link.startswith("https://"):
        return gg.failed("Choose a download link first")
    if not gg.signed_in():
        return gg.failed("LewdCorner shows download links to members: sign in on this plugin's Settings page first")
    try:
        t = thread(tid)
    except Blocked as e:
        return gg.failed(str(e))
    if t is None:
        return gg.failed("That thread is gone")
    if link not in [h for h, _ in t["links"]]:
        return gg.failed("That link is no longer in the thread; open it again")
    report(-1, "Opening %s in droidtop's browser view" % (urlparse(link).hostname or "the link"))
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


# ------------------------------------------------------------------ settings (C)


def settings_view(signed_in):
    items = [
        gg.info(
            "account",
            "LewdCorner account",
            "Signed in" if signed_in else "Not signed in",
            subtitle="You sign in on LewdCorner's own page in droidtop's browser view; this plugin never sees your password.",
        )
    ]
    if signed_in:
        items.append(gg.button("signout", "Sign out", gg.call_action("signOut")))
    else:
        items.append(gg.button("signin", "Sign in to LewdCorner", gg.job("signIn", "Sign in to LewdCorner")))
    items.append(gg.info("why", "Why sign in", subtitle="LewdCorner shows download links to members, and its Cloudflare check lets the plugin's requests through only with the session droidtop's browser view got."))
    return gg.view("LewdCorner", items)


@plugin.on("ui.settings", "view")
def _settings(args):
    return gg.ok(settings_view(gg.signed_in()))


@plugin.on("ui.settings", "signOut")
def _sign_out(args):
    gg.sign_out()
    return gg.ok({"message": "Signed out of LewdCorner", "view": settings_view(False)})


@plugin.job("ui.settings", "signIn")
def _sign_in(args, report):
    ok = gg.sign_in(LOGIN_URL, SIGNED_IN_COOKIE)
    return gg.done("Signed in to LewdCorner" if ok else "Not signed in")


handle, start_job, cancel_job = plugin.entry_points()
