# Changelog

Every working build of `main` is a release (`v<version>-<CI run>`); the
declared version moves with every change to the plugin's sources.

## 0.4.3

- A link under a heading that names no platform keeps that heading as its section ("Walkthrough: ...", or a line of its
  own such as "Save file" above it), so droidtop shows what the link is under it, in the Downloads tab's Extras or
  Other (Droidtop/tracker#617). Such links stay for every system.

## 0.4.2

- Each download link names its systems (Droidtop/tracker#617), for droidtop's system picker on the Downloads tab: the
  first post's heading over the link ("Win/Linux: ..." or a line of its own such as "Android") is the link's section,
  and the systems it names are its `systems`. A link under no platform heading ("Walkthrough") is left for every
  system.

## 0.4.1

- The release of 0.4.0's facets and contract 3 changes. 0.4.0's two commits shared one declared version, so CI's version rule refused the second
  and 0.4.0 was never released; this version carries both unchanged.

## 0.4.0

- On facets (droidtop docs/plugin-api.md 1.10): `ui.facets` declares `item.page`, so droidtop's update page for a
  linked thread is drawn from the thread's bundles: its metadata, the first post, its banner, the first post's download
  links (pages droidtop opens itself with the person's session) and the thread. Before, the page fell back to the
  older sheet, since the plugin had no `record`.
- The manifest says `"contractVersion": 3`: it needs facets, so a droidtop built before them refuses this version
  and keeps the one installed, rather than install a plugin whose settings it cannot draw (droidtop docs/plugin-api.md
  7, "Contract 3").

## 0.3.5

- A browser check answers `BROWSER_CHECK_REQUIRED` (droidtop docs/plugin-api.md 1.3, Droidtop/tracker#592): search,
  a thread and the scrape's `fetch` no longer return a made-up "Sign in" result or page. droidtop says the site checks
  the browser and offers Open the site, in its own web view with the plugin's session.
- droidtop draws the account (Droidtop/tracker#593): `web.session` declares LewdCorner's sign-in page and its
  signed-in cookie, and the plugin's own settings page (its "LewdCorner account" row, Sign in, Sign out) is gone, as
  are the sign-in rows on the search form. A thread still says to sign in to see its download links.

## 0.3.4

- The scrape's cover: `library.metadata fetch` names the first picture of the thread's first post on the forum itself
  (its banner) as `cover`, so a game with no cover gets it. droidtop fetches it itself, only from lewdcorner.com.
- Fewer requests to the forum: the scrape keeps a search's threads and a thread's metadata for a week in the plugin's
  data. Get games, game pages, downloads and update checks keep their own times.

## 0.3.3

- The scrape's text for a game (`library.metadata`, droidtop Droidtop/tracker#575): a game linked to its thread gets
  the thread's description and developer. An unlinked one is searched by its title and by its folder's name less
  version and platform ("Sample_Game-0.5-pc" is "Sample Game"), exact names only. One thread is the game; several
  with that name tie, and droidtop asks the person to pick. `fetch` names the thread (`sourceLinks`), so droidtop
  links the game to it. Needs the person signed in, as every LewdCorner page does.

## 0.3.2

- Names its kind for droidtop's Plugins page (`category`, docs/plugin-api.md 1.2, Droidtop/tracker#179).

## 0.3.1

- Declares the systems it serves (Windows and Linux games), so droidtop lists it in PC searches and not under a console such as Game Boy Advance.
  Needs a droidtop that reads `systems` on `library.sources` (docs/plugin-api.md 1.6); an older
  droidtop ignores the field and lists the source everywhere, as before.

## 0.3.0

- Signed-in searches no longer read as LewdCorner's browser check: every
  XenForo page carries "JavaScript is disabled" in a <noscript> notice,
  which the check test matched, so a signed-in person got the Sign in row
  instead of results.
- The site's own text never reaches the screen: flood control, members-only
  and HTTP failures are plain sentences.
- Shorter text: one-line description, sign-in and download hints, no "Why
  sign in" row; the detail page has its own Sign in button.
- Shared module 0.3.0 (contract 2.1 host names, needs droidtop
  0.2.0-dev.1767 or newer; smaller data reads).

## 0.2.1

- A browser-check page in place of the forum (Cloudflare's "Just a moment",
  or a "JavaScript is disabled" page as a BlueStacks rig got on build 1715) is
  recognised at any status, and also any answer without XenForo's page
  template. Get games then lists one row, "Sign in to LewdCorner", whose page
  says "LewdCorner needs you to sign in once in droidtop's browser view" with
  the Sign in action; the search form shows the same until you are signed in.
  Before, the search failed with the page's own text as droidtop's technical
  details.

## 0.2.0

- Open the thread opens it in your browser through Android's chooser
  (droidtop's apps.view, permission "Open links in other apps").

## 0.1.0

- First version: sign in and out on LewdCorner's own page in droidtop's
  browser view; Get games searches the Games forum's thread titles (or lists
  the latest threads); a thread's page shows its version, developer, tags and
  first-post download links, downloaded through droidtop's browser view with
  an engine hint; a game linked to its thread is checked for new versions,
  with a notification.
