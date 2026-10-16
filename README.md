# Stremio-LG-TV

A lightweight LG webOS launcher for the official [Stremio TV web interface](https://tv.strem.io/). Version **1.1.2** is a test build with a direct hosted-app launch and an optional recovery wrapper. It does not bundle Stremio or replace its player.

## Install the test build

Download the IPK from this repository's Releases page, then install it with [webOS TV Device Manager](https://github.com/webosbrew/dev-manager-desktop) and Developer Mode enabled on the TV. For a local build, select:

`dist/org.balazs.stremio-wrapper_1.1.2_all.ipk`

The app ID is unchanged from 1.0.0, so install it as an update. Keep the original IPK for reference. The new package contains only application resources and the license; the original 1.0.0 IPK also contained Git metadata.

**The reporter successfully tested version 1.1.2 on a physical LG OLED55CS TV.** Broader testing across webOS versions, standby/resume scenarios, remote Back behavior and media formats remains open.

## Startup and recovery

The launcher and recovery interface are English-only. Stremio opens directly after three seconds. Press any arrow to cancel automatic opening and choose an option with the arrows and OK:

- **Open Stremio** - direct launch, without an iframe.
- **Recovery mode** - keep the local recovery controls around an embedded Stremio page.
- **Exit** - request the platform Back/exit action.

If the TV reports that it is offline, automatic opening waits for a network connection. This is a network-interface hint, not a server/DNS/TLS health check. No extra requests are sent to Stremio's API or catalog as startup probes.

In recovery mode, the controls stay visible even after the page loads. When you can see Stremio's menus, select **Continue** to give its frame the remote's real keyboard input. If the logo remains, use **Retry** to recreate its browsing context, or **Open directly** to leave the wrapper. A message appears after 45 seconds; it never forces a reload during a slow startup or playback.

You can reopen recovery with the Magic Remote pointer using **Startup recovery**. With a directional remote, leave the app and return to it; visibility/relaunch events reopen the controls without reloading Stremio. This lifecycle behavior needs verification on the TV. Parent-page key handlers cannot receive keys while the foreign iframe has focus.

Direct launch unloads the local launcher. Its recovery controls and timers no longer exist after handover. If Stremio hangs in this mode, fully close the app, reopen it, press an arrow during the three-second startup window, and select recovery. Returning from Home may resume the existing app rather than restart the launcher.

Changing from iframe to direct launch changes the storage context and may require signing in again. The wrapper does not clear account data or cache. Retry resets the page's JavaScript context; it does not clear the TV's HTTP cache.

## What changed in 1.1.x

- Direct hosted-app handover is the default, with no nested frame during normal use.
- Added a small, remote-navigable launcher and manual recovery controls.
- Replaced ineffective iframe-error retries with visible, user-controlled recovery.
- Removed three redundant startup fetches, leaving only a connection hint for the UI host.
- Added online/offline and foreground/relaunch handling in the local wrapper.
- Removed forced focus on every window-focus event; focus is transferred at explicit UI and lifecycle transitions.
- Removed the stretched square splash background and used a solid splash color.
- Added an SDK-free, allowlisted, verified IPK build with SHA-256 output.
- Version 1.1.1 keeps the slow-start warning visible if a failed or delayed iframe load arrives after the timeout.
- Version 1.1.2 makes all launcher and recovery text English-only and aligns remote navigation with the left-to-right layout.

## Research and compatibility (2026-10-16)

The startup report and successful manual test concern an **LG OLED55CS** TV. LG lists the OLED55CS family among its [2022 models](https://www.lg.com/au/care-accessories/tvs/stand-wall-mount/olw480b/). Its exact installed firmware/webOS version has not been read from the TV. Compatibility with pre-2020 devices remains to be established separately.

| Evidence | Consequence |
| --- | --- |
| LG documents [hosted applications using top-level redirection](https://webostv.developer.lge.com/develop/getting-started/web-app-types). | Direct launch follows LG's documented model and removes nested-frame focus/storage variables. It is a plausible improvement, not a proven root-cause fix. |
| The [iframe specification behavior described by MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe#error_and_load_event_behavior) does not provide useful error events, and load may fire for failed documents. | The old retry handler could never be relied on. A load event also cannot establish that the remote SPA has passed its logo. |
| LG's [engine table](https://webostv.developer.lge.com/develop/specifications/web-api-and-web-engine) maps webOS 3.x/4.x to Chromium 38/53, and webOS 22 to Chromium 87. | Old-TV compatibility cannot be promised just because the wrapper uses ES5. Remote Stremio code has its own requirements. |
| LG documents [lifecycle resume/relaunch](https://webostv.developer.lge.com/develop/guides/app-lifecycle-management) and [Back handling](https://webostv.developer.lge.com/develop/guides/back-button). | Preserve the running frame on resume. Keep handlesRelaunch false so LG brings the app forward automatically. Native Back must be tested with Stremio focused. |
| Stremio [announced the official LG app's return for 2020+ models in August 2026](https://blog.stremio.com/stremio-for-lg-tv-is-back-2020-models-including-2026-models/). | An official app is an option for this TV family where the store region supports it. Availability on this particular TV has not been checked. |

The reporter confirms a successful manual TV test after the startup changes. The original intermittent hang has not been isolated to a single cause. Possible causes include network/DNS/TLS, a retained app after standby, remote Stremio initialization, and the TV's runtime/storage behavior. The wrapper cannot inspect or repair a foreign page's JavaScript, login state, catalog loading, or player internals.

A deeper webOS port would require access to the TV's Web Inspector and a separately scoped Stremio UI/player integration. Wrapping the remote page does not add codec, HDR, audio-track, subtitle, or DRM capabilities.

## Build and verify

GitHub Actions builds and tests the package on pushes to main, pull requests, and manual runs. Download the `webos-ipk` artifact from a successful run. Pushing a version tag also publishes a **prerelease** with the tested IPK and SHA-256 checksum; an unsuccessful build or test prevents publication.

To publish a new version, update `version` in appinfo.json, commit the source, then push a matching tag:

```powershell
git push origin main
git tag v1.1.2
git push origin v1.1.2
```

The tag must equal `v` followed by the manifest version. Existing releases and assets are never overwritten. Manual runs build artifacts only. Publishing uses GitHub's built-in token, so no personal access token or extra repository secret is needed. Release builds remain marked experimental until physical TV acceptance is complete.

Python 3.9+ is sufficient to build; no downloads or SDK are required:

```powershell
python tools/build_ipk.py
node --check main.js
```

The builder includes only appinfo.json, index.html, main.js, css/style.css, icon.png, LICENSE, and generated package metadata. It verifies the archive's contents against the current source bytes before writing the IPK and its checksum to dist/.

Browser checks use the Python Playwright package and an already installed Chromium:

```powershell
python -m unittest discover -s tests -v
```

These tests use simulated remote pages and cover direct handover, offline startup, network restoration, missing/failed loads, slow initialization, manual retry, actual keyboard delivery into a foreign frame, recovery-to-direct handover, foreground/relaunch, native exit API selection, and 1080p layout. The screenshots in artifacts/ are local development output.

## Further TV validation

Version 1.1.2 has a successful reporter-confirmed manual test on LG OLED55CS. The following scenarios have not been confirmed individually and remain useful for broader device qualification:

1. Install 1.1.2 and verify cold starts repeatedly, then repeat after standby and Home/app switching.
2. Compare direct and recovery modes; record which one stalls and whether the Stremio menus ever appear.
3. Start with the network disconnected, restore it, and check that retry is accessible.
4. Verify arrows, OK, short Back, platform exit, and Magic Remote pointer with Stremio focused.
5. Verify login persistence across a full close/reopen and across standby.
6. Play representative content and check seek, resume, subtitles, audio selection and HDR on the actual TV.

When a stall occurs, collect Web Inspector console and failed-request evidence without sharing account tokens, pairing codes, or signed stream URLs. That evidence is needed to identify the actual cause rather than repeatedly changing startup timers.
