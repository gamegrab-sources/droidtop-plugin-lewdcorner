# Changelog

Every working build of `main` is a release (`v<version>-<CI run>`); the
declared version moves with every change to the plugin's sources.

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
