package com.gatearmy.game;

import android.annotation.SuppressLint;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;
import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.webkit.WebViewAssetLoader;
import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.RequestConfiguration;
import com.google.android.gms.ads.rewarded.RewardedAd;
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback;
import com.google.android.ump.ConsentInformation;
import com.google.android.ump.ConsentRequestParameters;
import com.google.android.ump.UserMessagingPlatform;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;

/** Hosts only packaged content. Native Google ads never run inside the game's WebView. */
public final class MainActivity extends ComponentActivity {
    private static final String ORIGIN = "https://appassets.androidplatform.net";
    private WebView web;
    private ConsentInformation consent;
    private SharedPreferences settings;
    private RewardedAd rewarded;
    private boolean pageReady, initialized, loading, showing, consentStarted, changingPrivacy;
    private int adEpoch;
    private String reason = "Ads are loading. You can always play without them.";

    @SuppressLint("SetJavaScriptEnabled")
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        settings = getSharedPreferences("privacy", MODE_PRIVATE);
        consent = UserMessagingPlatform.getConsentInformation(this);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(16,23,39));
        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(-1,-1));
        setContentView(root);
        // API 36 enforces edge-to-edge. Keep gameplay clear of system bars/cutouts.
        ViewCompat.setOnApplyWindowInsetsListener(root, (v,insets) -> {
            androidx.core.graphics.Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            v.setPadding(bars.left,bars.top,bars.right,bars.bottom);
            return insets;
        });
        WebSettings ws = web.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setAllowFileAccess(false);
        ws.setAllowContentAccess(false);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        ws.setMediaPlaybackRequiresUserGesture(true);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        web.addJavascriptInterface(new AdsBridge(), "AndroidAds");
        WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
            .addPathHandler("/assets/",new WebViewAssetLoader.AssetsPathHandler(this)).build();
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                WebResourceResponse local = loader.shouldInterceptRequest(req.getUrl());
                if (local != null) return local;
                // No remote scripts, frames, fonts, trackers, or arbitrary web browsing.
                return new WebResourceResponse("text/plain","UTF-8",403,"Blocked",null,new ByteArrayInputStream(new byte[0]));
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest req) {
                Uri url = req.getUrl();
                if ("mailto:youaramusha@gmail.com".equals(url.toString())) {
                    try { startActivity(new Intent(Intent.ACTION_SENDTO,url)); } catch(Exception ignored) {}
                    return true;
                }
                return !(ORIGIN.equals(url.getScheme()+"://"+url.getAuthority()) && url.getPath()!=null && url.getPath().startsWith("/assets/"));
            }
            @Override public void onPageFinished(WebView view,String url) {
                pageReady = true;
                sendStatus();
                if (!consentStarted) { consentStarted = true; chooseAgeAndConsent(); }
            }
        });
        getOnBackPressedDispatcher().addCallback(this,new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                pauseGame();
                new AlertDialog.Builder(MainActivity.this).setTitle("Leave Gate Army?")
                    .setMessage("Completed missions are saved. The current run will restart next time.")
                    .setNegativeButton("Keep playing",null).setPositiveButton("Leave",(d,w)->finish()).show();
            }
        });
        web.loadUrl(ORIGIN+"/assets/index.html");
    }

    private boolean adult() { return settings.getBoolean("adult",false); }
    private void chooseAgeAndConsent() {
        if (settings.contains("adult")) { beginConsent(); return; }
        new AlertDialog.Builder(this).setTitle("Choose your age group")
            .setMessage("Gate Army is intended for ages 13 and up. Players under 18 play without advertising. We save only this age group on your device.")
            .setCancelable(false)
            .setNegativeButton("Under 18",(d,w)->{settings.edit().putBoolean("adult",false).apply();beginConsent();})
            .setPositiveButton("18 or older",(d,w)->{settings.edit().putBoolean("adult",true).apply();beginConsent();})
            .show();
    }
    private void beginConsent() {
        if (!adult()) {reason="Ads are disabled for players under 18.";sendStatus();return;}
        ConsentRequestParameters params = new ConsentRequestParameters.Builder().setTagForUnderAgeOfConsent(false).build();
        consent.requestConsentInfoUpdate(this,params,
            () -> UserMessagingPlatform.loadAndShowConsentFormIfRequired(this,error -> {
                if (consent.canRequestAds()) initializeAds();
                else { reason="Ads are unavailable with the current privacy settings."; sendStatus(); }
            }), error -> {
                // Cached permission can remain valid when the consent service is offline.
                if (consent.canRequestAds()) initializeAds();
                else { reason="Ads are unavailable. Please try again when connected.";sendStatus(); }
            });
    }
    private void initializeAds() {
        if (!adult() || !consent.canRequestAds() || isFinishing()) return;
        if (initialized) { loadRewarded(); return; }
        initialized=true;
        MobileAds.setRequestConfiguration(new RequestConfiguration.Builder()
            .setMaxAdContentRating(RequestConfiguration.MAX_AD_CONTENT_RATING_T)
            .setTagForChildDirectedTreatment(RequestConfiguration.TAG_FOR_CHILD_DIRECTED_TREATMENT_FALSE)
            .setTagForUnderAgeOfConsent(RequestConfiguration.TAG_FOR_UNDER_AGE_OF_CONSENT_FALSE).build());
        new Thread(() -> MobileAds.initialize(this, status -> runOnUiThread(this::loadRewarded))).start();
    }
    private void loadRewarded() {
        if (!adult() || !consent.canRequestAds() || changingPrivacy || loading || rewarded!=null || isFinishing() || isDestroyed()) return;
        loading=true;
        final int requestEpoch=adEpoch;
        RewardedAd.load(this,BuildConfig.REWARDED_ID,new AdRequest.Builder().build(),new RewardedAdLoadCallback() {
            @Override public void onAdLoaded(RewardedAd ad) {
                if (requestEpoch!=adEpoch) return;
                loading=false;
                if (!adult() || !consent.canRequestAds() || isDestroyed()) return;
                rewarded=ad;reason="Watch an optional ad for 15 soldiers on your next run.";sendStatus();
            }
            @Override public void onAdFailedToLoad(LoadAdError error) {
                if (requestEpoch!=adEpoch) return;
                loading=false;rewarded=null;reason="No ad is available right now. You can keep playing.";sendStatus();
            }
        });
    }
    private void sendStatus() {
        try {
            JSONObject event=new JSONObject().put("type","status").put("ready",rewarded!=null && !showing && adult() && consent.canRequestAds())
                .put("eligible",adult()).put("test",BuildConfig.DEBUG).put("message",reason);
            send(event);
        } catch(Exception ignored) {}
    }
    private void send(JSONObject event) {
        if (pageReady && !isDestroyed()) web.evaluateJavascript("window.GateAdsNative && window.GateAdsNative.receive("+event+")",null);
    }
    private void respond(String id, boolean earned, String message) {
        try { send(new JSONObject().put("type","reward").put("id",id).put("earned",earned).put("message",message)); } catch(Exception ignored) {}
    }
    private void showReward(String id) {
        if (!id.matches("reward-[0-9]+")) return;
        if (showing || rewarded==null || !adult() || !consent.canRequestAds()) {
            respond(id,false,"No ad is available. Your next run is still free.");loadRewarded();return;
        }
        showing=true;
        RewardedAd ad=rewarded;rewarded=null;sendStatus();
        final boolean[] earned={false};
        ad.setFullScreenContentCallback(new FullScreenContentCallback() {
            @Override public void onAdDismissedFullScreenContent() {
                showing=false;respond(id,earned[0],earned[0]?"15 soldiers added to your next run.":"Ad closed without a reward.");loadRewarded();sendStatus();
            }
            @Override public void onAdFailedToShowFullScreenContent(AdError error) {
                showing=false;respond(id,false,"The ad could not play. Please continue your game.");loadRewarded();sendStatus();
            }
        });
        ad.show(this,reward -> earned[0]=true);
    }
    private final class AdsBridge {
        @JavascriptInterface public void refresh() { runOnUiThread(()->{sendStatus();if(initialized)loadRewarded();}); }
        @JavascriptInterface public void reward(String id) { runOnUiThread(()->showReward(id)); }
        @JavascriptInterface public void privacy() { runOnUiThread(()->{
            if(!adult()) { Toast.makeText(MainActivity.this,"Advertising is disabled for your age group.",Toast.LENGTH_LONG).show();return; }
            if(consent.getPrivacyOptionsRequirementStatus()!=ConsentInformation.PrivacyOptionsRequirementStatus.REQUIRED) {
                Toast.makeText(MainActivity.this,"No additional advertising privacy form is required in your region.",Toast.LENGTH_LONG).show();return;
            }
            adEpoch++;loading=false;rewarded=null;changingPrivacy=true;sendStatus();
            UserMessagingPlatform.showPrivacyOptionsForm(MainActivity.this,error->{changingPrivacy=false;if(error!=null)Toast.makeText(MainActivity.this,"Privacy options could not load. Try again online.",Toast.LENGTH_LONG).show();if(consent.canRequestAds())initializeAds();sendStatus();});
        }); }
        @JavascriptInterface public void policy() { runOnUiThread(()->{
            if(BuildConfig.PRIVACY_URL.startsWith("https://")) {
                try { startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(BuildConfig.PRIVACY_URL))); } catch(Exception ignored) {}
            } else Toast.makeText(MainActivity.this,"Development build: the public privacy URL is not configured yet.",Toast.LENGTH_LONG).show();
        }); }
    }
    private void pauseGame() { if(pageReady)web.evaluateJavascript("window.GateNativeLifecycle && window.GateNativeLifecycle.pause()",null); }
    @Override protected void onPause() { pauseGame();super.onPause();if(web!=null)web.onPause(); }
    @Override protected void onResume() { super.onResume();if(web!=null)web.onResume(); }
    @Override protected void onDestroy() { adEpoch++;rewarded=null;pageReady=false;if(web!=null){web.removeJavascriptInterface("AndroidAds");web.destroy();}super.onDestroy(); }
}
