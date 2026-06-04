"""
Social posting module — posts to Facebook Page + Instagram Business via Meta Graph API.

Reads all credentials from environment variables (set in Railway — never hardcoded):
  META_ACCESS_TOKEN   - System User token (never expires) with pages_manage_posts + instagram_content_publish
  META_PAGE_ID        - Facebook Page ID (1191605287359477)
  META_IG_USER_ID     - Instagram Business Account ID (fetched via /me/accounts)

Facebook: text posts work directly.
Instagram: requires a public image URL (IG has no text-only posts) — we generate a
branded image, host it under /static, and pass its Railway public URL.
"""
import os
import time
import requests

GRAPH = "https://graph.facebook.com/v21.0"

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")   # direct page/system-user token (optional)
META_PAGE_ID = os.getenv("META_PAGE_ID")
META_IG_USER_ID = os.getenv("META_IG_USER_ID")

# For auto-deriving a PERMANENT page token from a user token (recommended path)
APP_ID = os.getenv("META_APP_ID", "969898192329367")
APP_SECRET = os.getenv("APP_SECRET")
META_USER_TOKEN = os.getenv("META_USER_TOKEN")

_cached_page_token = None


def _exchange_for_long_lived(short_token):
    """Exchange a short-lived user token for a long-lived one (60 days)."""
    r = requests.get(f"{GRAPH}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": short_token,
    }, timeout=20).json()
    return r.get("access_token")


def _page_token_from_user(user_token):
    """Get the Page access token for META_PAGE_ID. Derived from a long-lived
    user token, this page token does NOT expire."""
    r = requests.get(f"{GRAPH}/me/accounts",
                     params={"access_token": user_token, "fields": "id,access_token"},
                     timeout=20).json()
    for page in r.get("data", []):
        if page.get("id") == META_PAGE_ID:
            return page.get("access_token")
    return None


def get_page_token():
    """
    Resolve the effective Facebook Page token:
      1) If META_ACCESS_TOKEN is set directly (system-user/page token), use it.
      2) Else derive a permanent page token from META_USER_TOKEN + APP_SECRET.
    Cached after first successful resolution.
    """
    global _cached_page_token
    if META_ACCESS_TOKEN:
        return META_ACCESS_TOKEN
    if _cached_page_token:
        return _cached_page_token
    if META_USER_TOKEN and APP_SECRET and META_PAGE_ID:
        try:
            long_token = _exchange_for_long_lived(META_USER_TOKEN) or META_USER_TOKEN
            page_token = _page_token_from_user(long_token)
            if page_token:
                _cached_page_token = page_token
                return page_token
        except Exception as e:
            print(f"Token resolution failed: {e}")
    return None


def is_configured():
    """True if we can resolve a Facebook posting token."""
    return bool(get_page_token() and META_PAGE_ID)


def post_to_facebook(message, link=None):
    """
    Post a text update (optionally with a link) to the Facebook Page.
    Returns {"ok": bool, "id"/"error": ...}.
    """
    token = get_page_token()
    if not (token and META_PAGE_ID):
        return {"ok": False, "error": "Facebook not configured (missing token/page id)"}

    payload = {"message": message, "access_token": token}
    if link:
        payload["link"] = link

    try:
        resp = requests.post(f"{GRAPH}/{META_PAGE_ID}/feed", data=payload, timeout=30)
        data = resp.json()
        if resp.status_code == 200 and "id" in data:
            return {"ok": True, "id": data["id"]}
        return {"ok": False, "error": data.get("error", data)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def post_photo_to_facebook(image_url, caption):
    """
    Post a PHOTO (branded card) with caption to the Facebook Page.
    Looks far more polished than text-only. Returns {"ok": bool, "id"/"error": ...}.
    """
    token = get_page_token()
    if not (token and META_PAGE_ID):
        return {"ok": False, "error": "Facebook not configured"}
    try:
        resp = requests.post(
            f"{GRAPH}/{META_PAGE_ID}/photos",
            data={"url": image_url, "caption": caption, "access_token": token},
            timeout=40,
        ).json()
        if "id" in resp or "post_id" in resp:
            return {"ok": True, "id": resp.get("post_id", resp.get("id"))}
        return {"ok": False, "error": resp.get("error", resp)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def post_to_instagram(image_url, caption):
    """
    Post an image to Instagram Business account (2-step: create container, then publish).
    image_url must be a PUBLIC url that Meta can fetch (e.g. Railway static URL).
    Returns {"ok": bool, "id"/"error": ...}.
    """
    token = get_page_token()
    if not (token and META_IG_USER_ID):
        return {"ok": False, "error": "Instagram not configured (missing token/ig user id)"}

    try:
        # Step 1: create media container
        create = requests.post(
            f"{GRAPH}/{META_IG_USER_ID}/media",
            data={"image_url": image_url, "caption": caption, "access_token": token},
            timeout=30,
        ).json()

        if "id" not in create:
            return {"ok": False, "error": create.get("error", create)}

        creation_id = create["id"]
        # Give Meta a moment to fetch/process the image
        time.sleep(3)

        # Step 2: publish the container
        publish = requests.post(
            f"{GRAPH}/{META_IG_USER_ID}/media_publish",
            data={"creation_id": creation_id, "access_token": token},
            timeout=30,
        ).json()

        if "id" in publish:
            return {"ok": True, "id": publish["id"]}
        return {"ok": False, "error": publish.get("error", publish)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def fetch_ig_user_id():
    """
    Helper to fetch the Instagram Business Account ID once a valid token is set.
    Run this after configuring META_ACCESS_TOKEN to get META_IG_USER_ID.
    """
    token = get_page_token()
    if not (token and META_PAGE_ID):
        return None
    try:
        resp = requests.get(
            f"{GRAPH}/{META_PAGE_ID}",
            params={"fields": "instagram_business_account", "access_token": token},
            timeout=15,
        ).json()
        return resp.get("instagram_business_account", {}).get("id")
    except Exception as e:
        print(f"Error fetching IG user id: {e}")
        return None


def publish_post(fb_message, ig_image_url=None, ig_caption=None, link=None):
    """
    Publish the same post to both platforms.
    Returns {"facebook": {...}, "instagram": {...}}.
    """
    results = {}
    results["facebook"] = post_to_facebook(fb_message, link=link)
    if ig_image_url and ig_caption:
        results["instagram"] = post_to_instagram(ig_image_url, ig_caption)
    else:
        results["instagram"] = {"ok": False, "error": "No image/caption provided"}
    return results
