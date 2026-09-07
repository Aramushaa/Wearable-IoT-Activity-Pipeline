# Data safety review notes — not a submitted declaration

Publisher: Sleepy Panda Games. Support: youaramusha@gmail.com.

## First-party behavior

- Local-only progress, medals, outfit, reward balance, and age category; no player account, cloud save, purchase, chat, location access, publisher analytics, or gameplay backend.
- Android backup disabled. Deletion: clear app storage or uninstall; browser version: clear site storage.
- Contact email opens the email client. Support messages are voluntarily sent outside the app and handled as described in the policy.
- All game assets and fonts packaged locally. No Google Fonts requests remain.

## Android advertising

Google Mobile Ads 25.4.0 and UMP 4.0.0 are included. SDK initialization/loading is gated on adulthood selection and UMP's canRequestAds() result. No ad mediation adapters or Firebase Analytics are added. The advertising SDK may contribute its own permissions/dependencies; inspect the merged manifest and final bundle.

Google documents automatic collection/sharing of IP addresses (potential approximate location), app/ad interactions, diagnostics, and device/account identifiers for advertising, analytics, and fraud prevention. Those need review in the Play Console categories (including approximate location, app activity/interactions, app information/performance, and device or other IDs). Do **not** declare “no data collected” merely because your gameplay state stays local. Google's SDK disclosure documents encryption in transit. Do not claim SDK data is automatically deleted when local app storage is cleared.

The publisher must decide optional/required collection flags, specific purposes, sharing exceptions, retention/deletion representations, and region-dependent behavior based on the final tested configuration and current form. A privacy consent dialog alone does not complete Data safety.

Audience choices: intended 13+, ads disabled under 18. Answer the content-rating form accurately for fantasy weapons and stylized combat without blood; the assigned rating is determined by the form. Declare **Contains ads: Yes**, even though ads are optional and adult-only. Complete the Advertising ID declaration based on the merged manifest; the included SDK declares AD_ID.

Review the public privacy policy and publish UMP messages before release. Verify both rejection and consent-withdrawal paths, and that stale loaded ads are discarded when privacy choices change.

Sources: [Google SDK disclosure](https://developers.google.com/admob/android/privacy/play-data-disclosure), [UMP](https://developers.google.com/admob/android/privacy), [Play policy center](https://play.google.com/about/developer-content-policy/).
