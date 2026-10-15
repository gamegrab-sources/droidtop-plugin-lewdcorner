# droidtop-plugin-lewdcorner

An **unofficial** plugin for [droidtop](https://github.com/Droidtop/droidtop) from
gamegrab-sources. It is not part of droidtop and is not affiliated with
LewdCorner.

LewdCorner is a XenForo forum like F95zone, so this plugin works like
[droidtop-plugin-f95](https://github.com/gamegrab-sources/droidtop-plugin-f95),
with the forum itself as its only source.

## What it does

- **Sign in** (Settings): on LewdCorner's own page, in droidtop's browser view.
  The plugin never sees your password. The site sits behind a Cloudflare check
  and shows download links to members, so the plugin's requests go with the
  session droidtop's browser view got; without it, they are refused.
- **Get games** (droidtop's `library.sources`): searches thread titles in the
  Games forum, or lists its latest updated threads when the search is empty.
  Results show the version, developer and prefixes (engine, status).
- **A thread** shows its version, developer, tags, the start of its first post,
  and the download links in that post. A link opens in droidtop's browser view
  with your session; go through the file host's page yourself, and the download
  it starts runs in droidtop's Downloads into your game folder. Ren'Py, HTML,
  Godot, Unity and Unreal threads carry an engine hint, so droidtop opens the
  game with that engine's player.
- **Updates** (droidtop's `library.updates`, "LewdCorner thread"): link a game to
  its thread (paste the link or number, or pick from matches) and droidtop's
  update round reads the thread's title for the current version, one thread
  every 2 seconds, at most 90 seconds a round; a notification says when a
  linked game has a new version.

## Permissions

- Connect to lewdcorner.com.
- Use your signed-in session on lewdcorner.com.
- Notifications, and adding files to your game folders.
- Open links in other apps (a thread, in your browser).

It runs contained in droidtop (no network or files of its own).

## Building

`./build.sh` writes `build/manifest.json` and `build/plugin.py` (the source with
the shared `gamegrab` module from the `common` submodule embedded); `./sign.sh`
signs and packs it. CI does both and publishes every working build of `main` as
a release; the gamegrab-sources catalog lists it from there. Tests:
`python3 common/test_gamegrab.py && python3 test_plugin.py`.

## Licence

GPL-3.0, see LICENSE and NOTICE.

## Signing

The bundle carries `manifest.jws`: a detached ES256 JWS over the exact bytes of `manifest.json`, with this repository's leaf certificate in `x5c` (the root itself is not included). The leaf comes from the repository secrets `PLUGIN_SIGNING_KEY` and `PLUGIN_SIGNING_CERT` and was issued by the gamegrab root, a third-party anchor that people choose to trust (it is not pinned by the droidtop app); it names the plugin's origin and id. `sign_jws.py` writes the signature and checks it against the leaf before packing. `manifest.sig` stays in the bundle for older droidtop builds. Expiry dates are not checked.

`droidtop-plugin-key.json` in the repository root carries the gamegrab root certificate; droidtop reads it to anchor the `gamegrab` origin at that root.
