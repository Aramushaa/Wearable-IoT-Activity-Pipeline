# Publishing Gate Army: Five Empires

Prepared for Sleepy Panda Games • youaramusha@gmail.com • September 5, 2026

## Current state — not published

The web game, native Android project, native AdMob rewarded integration, age-group restriction, UMP consent flow, policy draft, store copy, and release artwork are prepared. Debug uses Google's official test IDs. No real ad IDs, developer account, payments, signing key, public policy site, or store submission have been created.

The Android app has **not yet been compiled or tested on a device**. This computer has Java and Gradle, but no Android SDK was found. An attempted Gradle configuration also could not download the Android build plugin; a direct request to Google's Maven host failed TLS validation. Do not disable certificate checking to work around this. Configure a trusted network/Android Studio environment first.

## 1. Your account steps

1. Create a [Google Play Console developer account](https://play.google.com/console/signup). Use the correct personal or organization account for your actual status. A studio display name does not itself mean you have a registered organization. The account holder must be 18 or older.
2. Pay Google's **US$25 one-time registration fee**, accept its agreement, and complete the required identity/contact verification. Google may require an Android-device verification for a new personal account. Enter ID, bank, tax, and password details directly into Google's own site, not this chat.
3. Create a [Google AdMob account](https://admob.google.com/home/). Complete its country, identity, payment, and tax steps as requested. Your country is still needed to check eligibility and the relevant setup path.
4. In AdMob, create an Android app named Gate Army: Five Empires. Create a **Rewarded** ad unit with a reward of **15 soldiers**. The publisher ID, app ID, and ad-unit ID are different values. Only those public IDs are needed for configuration; no login credentials are needed.

## 2. Website, privacy and verification

- Use a website you control with a public HTTPS address. No domain has been provided yet.
- Publish the prepared privacy.html there after reviewing it. Enter its URL in Play Console and in android/release.properties. Add the studio website to the Play listing's developer website field.
- In AdMob, copy the exact app-ads.txt record supplied for your publisher account to the website root: `https://YOUR-WEBSITE/app-ads.txt`. The line normally has the form `google.com, pub-YOUR-PUBLISHER-ID, DIRECT, f08c47fec0942fa0` — replace the publisher value with the exact account value. A placeholder file must not be published.
- Complete app ownership verification and AdMob's app readiness review. New apps need these checks for full ad serving.
- In AdMob Privacy & messaging, create and publish the applicable European-regulations message and any relevant US-state privacy messages. Link the app's real AdMob ID. Configure the messages for your actual release regions. UMP is already wired into the Android project, but account-side messages still must be configured and tested.
- The first release serves ads only to users who select 18 or older. Choosing under 18 disables ad initialization and requests. No birth date is collected. Do not broaden this behavior without revisiting the audience, privacy and ad configuration.

## 3. Build and sign

1. Install [Android Studio](https://developer.android.com/studio), review/accept its SDK terms yourself, then install Android SDK Platform 36, SDK Build-Tools 35.0.0 (or the version requested by the project), and Platform-Tools. Use Android Studio's compatible JDK (17+).
2. From the gate-army folder, run `npm ci`, `npm test`, then `npm run android:prepare`. Fonts and game assets are packaged locally; the app needs no game server.
3. Open the `android` folder as an Android Studio project. Allow Gradle synchronization. Build and run the **debug** variant on your Android phone first. Its package ID ends in `.debug` and it uses Google's test ads. Test ads produce no revenue. Never click your own production ads.
4. Copy `android/release.properties.example` to `android/release.properties`. Set your production AdMob app ID, rewarded ad-unit ID, and published privacy URL. Confirm `com.sleepypandagames.gatearmy` as the final package ID before the first upload; it cannot later be changed for the same store listing.
5. Use Android Studio's **Generate Signed App Bundle / APK → Android App Bundle**. Create and securely back up your upload keystore and passwords. Choose the release variant and enroll in Play App Signing when uploading. Signing passwords and keystores must stay outside source control. The release build rejects test ad IDs and incomplete configuration.
6. For command-line signing, supply `GATE_ARMY_KEYSTORE`, `GATE_ARMY_STORE_PASSWORD`, `GATE_ARMY_KEY_ALIAS`, and `GATE_ARMY_KEY_PASSWORD` locally, then run `gradlew.bat :app:bundleRelease`. Never put passwords in chat, shell history, or committed files.
7. The expected bundle is `android/app/build/outputs/bundle/release/app-release.aab`. Increase versionCode for every subsequent upload.

## 4. Verify on real devices

- Fresh install, age-group choice, under-18 ad-free path, adult privacy form, accept/refuse/manage-consent paths. Use AdMob's official test-device settings to exercise required geographies; do not add fake geography to production.
- Rewarded ad earned/closed/failed/no-fill/offline paths. Verify that only a completed reward grants 15 soldiers, it cannot stack, and it is consumed once at the next run.
- All five missions, outfits, medals, music mute, pause, background/foreground, Android Back, system bars, notches, and landscape/tablet layouts.
- Real network loss, app process death, reinstall/clear-data behavior, and performance with the largest army. Check Android logs and Play's pre-launch report for crashes/ANRs.
- Verify the merged manifest and bundled SDK libraries, including current 16 KB page-size compatibility and 64-bit requirements if any dependency introduces native libraries. The game's own code has no native .so libraries. npm's artwork library is development-only and is not packaged.
- Capture actual phone screenshots from this final build. Do not substitute the review renders for genuine device screenshots.

## 5. Play Console release

Create the app as **Game → Free**, in English, with the prepared name and developer name. Set **Contains ads: Yes**. Upload the signed bundle to internal testing, then complete store assets, support details, privacy URL, target audience, content rating, advertising-ID declaration, and Data safety. Use data-safety-notes.md as a review aid, not an automatic declaration.

New personal accounts created after November 13, 2023 must generally run a closed test with **12 testers opted in continuously for 14 days**, then apply for production access. Recruit genuine testers and record feedback/fixes. The elapsed time alone does not guarantee production approval. Organization accounts follow their own verification/testing path.

After testing, fix issues, review the complete listing and declarations, then submit the production release. Google decides approval. Connect the published store listing to AdMob and finish app readiness/app-ads.txt verification. Keep test builds on test ads throughout testing.

Run `npm run release:check` to see the remaining local checklist. Update release/publisher.json only after each item is actually complete; ticking it is not a substitute for the external verification.

## Costs and revenue

Google Play account registration is a one-time US$25 fee. AdMob has no signup fee. Identity verification, applicable taxes, optional domain/hosting, device costs, and marketing are separate. Publishing a game does not guarantee downloads or earnings.

Estimated ad revenue = **actual ad impressions ÷ 1,000 × publisher eCPM**. As a purely illustrative scenario, two actual ad impressions per daily player at a US$5 eCPM over 30 days would yield about $30/month for 100 daily players, $300 for 1,000, or $3,000 for 10,000. These are arithmetic examples, not a forecast or market benchmark. This game uses voluntary adult-only ads, so many players will generate zero impressions. Country mix, consent, ad demand, retention, fill rate, and season affect actual earnings; it may be zero. Downloads alone are not paid.

## Official references checked September 5, 2026

- [Registration, fee, verification](https://support.google.com/googleplay/android-developer/answer/6112435?hl=en)
- [Personal-account testing](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en)
- [Current target API requirements — API 36 for new mobile apps](https://developer.android.com/google/play/requirements/target-sdk)
- [AdMob setup](https://developers.google.com/admob/android/quick-start)
- [UMP privacy flow](https://developers.google.com/admob/android/privacy)
- [AdMob data disclosures](https://developers.google.com/admob/android/privacy/play-data-disclosure)
- [Store artwork requirements](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en)
- [eCPM explanation](https://support.google.com/admob/answer/15337570?hl=en)
