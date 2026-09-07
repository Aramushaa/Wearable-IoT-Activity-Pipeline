# Gate Army

A self-contained mobile browser game: lead an army across five fantasy islands ruled by rival sovereigns. The browser version runs without a build step. Android packaging and store-art generation use the included development tools.

## The islands campaign

- Laurel Imperium (Roman), Aegean Acropolis (Greek), Saffron Palace (Persian), Temple of Dawn (Egyptian), and Frosthold Fjord (Norse) each have their own ruler, palette, architecture, banners, briefing, and victory story.
- Arithmetic gates grow or shrink the squad. Three consecutive growth gates start a streak that awards five extra soldiers per subsequent growth gate.
- Each rescued scout group adds 15 soldiers. Rescue both groups for a bonus medal.
- Shield pickups absorb one obstacle or patrol hit. Shields do not stack or protect against negative gates.
- Later missions introduce moving saws, enemy patrols, and faster runs.
- Final battles include a single rally strike. Tap while the timing marker is in the green zone to remove 32% of the initial enemy army; otherwise the strike removes 12%.
- Earn one medal for victory, one for rescuing both groups, and one for meeting the mission's survivor target. Best medals, unlocked missions, and peak squad size save locally in the browser.
- Replay unlocked missions from the mission list beside the game (below it on phones). Pause to resume or restart.

Open `index.html` in a modern browser, or serve this directory with any static web server. Touch: drag horizontally. Desktop: move the mouse over the game or use arrow keys / A and D. Space pauses. Tap the rally button or press R during battle.

The game and licensed fonts work offline. An Android source project is included, but a signed app bundle has not yet been built or device-tested. Optional native rewarded ads need internet access, valid consent, and production account configuration.

## Verification

Run `npm test` from this folder. The isolated simulation checks arithmetic, streak bonuses, shield consumption, damage, pausing, all five three-medal routes, single-use rally, campaign saving, defeat, restart, and canvas drawing calls. Browser visual checks complement these simulation checks.

## Five Empires graphics and sound

- Detailed animated outfits include different helmets, armor, shields, weapons, and a standard bearer. Enemy armies wear the island's outfit with dark crimson identification colors.
- The wardrobe below the game offers large previews of all five outfits. Match the island automatically or choose one outfit for every mission. Your choice saves locally and does not change combat strength.
- Roman arcades, Greek temples, Persian-inspired palaces, Egyptian pyramids, and Norse halls appear on the islands and at their final encounters. These are stylized fantasy designs with fictional rulers, not historical reconstructions.
- Enable the sound button for original synthesized melodies, bass and drums, and distinct action effects. Battle music runs at a faster tempo. Music fades while paused and the mute button silences music and effects together. Sound begins only after a user gesture.
- Run `node audio.test.cjs` to check audio activation, each island's score, effects, pause, mute, and re-enabling sound. No audio files or external music services are needed.

## Google Play preparation

See [the publishing guide](release/PUBLISHING.md) for the exact status, owner account steps, Android setup, ad configuration, signing, testing, and submission checklist. Store artwork and copy are in `release/`; the privacy draft is `privacy.html`.

Rewarded ads are optional, Android-only, and restricted to players selecting 18 or older. A verified reward supplies 15 soldiers for the next run, once, without stacking. Browser previews never simulate ad earnings. Debug builds use Google's test ad IDs, and release validation rejects test IDs.

`npm run android:prepare` packages the current game and fonts into the Android app. `npm run release:check` intentionally fails until accounts, public policy/website, production IDs, testing, and a signed bundle are complete. Do not submit unfinished checklist declarations.
