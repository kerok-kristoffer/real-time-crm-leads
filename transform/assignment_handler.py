import os, json, time, random
import urllib.parse, urllib.request, urllib.error

from botocore.exceptions import ClientError
import boto3

# --- Environment / constants ---
SKIP_OWNER_LOOKUP = os.getenv("SKIP_OWNER_LOOKUP", "false").lower() == "true"
OWNER_BASE        = os.environ["OWNER_BASE"]
CURATED_BUCKET    = os.environ["CURATED_BUCKET"]
ERROR_BUCKET      = os.environ["ERROR_BUCKET"]

RAW_PREFIX        = "crm/lead_created"
CURATED_PREFIX    = "crm/lead_enriched"
ERR_PREFIX        = "crm/errors"

RETRY_TRANSIENT   = 2  # small in-function retries for transient HTTP issues

# --- Clients (reuse across invokes) ---
s3 = boto3.client("s3")
secrets = boto3.client("secretsmanager")

# --- Helpers ---
def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

def _read_json_from_s3(bucket, key):
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())

def _write_json_to_s3(bucket, key, payload):
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )

def classify_lookup_error(err: Exception) -> str:
    """Return 'permanent' | 'transient' | 'unknown' based on HTTP error semantics."""
    if isinstance(err, urllib.error.HTTPError):
        if 400 <= err.code < 500:
            return "permanent"   # 404/403/400 etc. won’t heal
        if 500 <= err.code < 600:
            return "transient"
    if isinstance(err, urllib.error.URLError):
        return "transient"
    return "unknown"

def fetch_owner_json(owner_url: str) -> dict:
    """Fetch owner JSON with tiny local retries for transient issues."""
    last = None
    for _ in range(RETRY_TRANSIENT + 1):
        try:
            with urllib.request.urlopen(owner_url, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception as e:
            last = e
            if classify_lookup_error(e) == "permanent":
                raise
            # transient: small scattered backoff
            time.sleep(0.4 + random.random() * 0.4)
    # bubble up as transient/unknown
    raise last

def _write_error_artifact(day: str, lead_id: str, reason: str, extra: dict | None = None):
    key = f"{ERR_PREFIX}/dt={day}/lead_id={lead_id}/owner_lookup_failed.json"
    payload = {
        "lead_id": lead_id,
        "reason": reason,
        "at": _now_iso(),
    }
    if extra:
        payload.update(extra)
    _write_json_to_s3(ERROR_BUCKET, key, payload)

# --- Slack setup ---

SLACK_SECRET_NAME = os.getenv("SLACK_SECRET_NAME")  # from Lambda env
_slack_url_cache = None

def _slack_url() -> str | None:
    if not SLACK_SECRET_NAME:
        return None
    try:
        sec = secrets.get_secret_value(SecretId=SLACK_SECRET_NAME)
        val = sec.get("SecretString") or "{}"
        data = json.loads(val)
        url = data.get("url") or data.get("webhook") or data.get("SLACK_WEBHOOK_URL")
        return url
    except Exception as e:
        print(f"[slack] failed to read secret {SLACK_SECRET_NAME}: {e}")
        return None

def _post_slack(webhook_url: str, payload: dict) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", "ignore")
            return resp.getcode(), body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        return e.code, body
    except Exception as e:
        return 0, str(e)

# --- Handler ---
def lambda_handler(event, context):
    # SQS event → each record body may be raw S3 event or SNS-wrapped S3 event
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        s3_event = json.loads(body.get("Message")) if "Message" in body else body

        for rec in s3_event.get("Records", []):
            bucket = rec["s3"]["bucket"]["name"]
            key    = urllib.parse.unquote_plus(rec["s3"]["object"]["key"])

            # Expect: crm/lead_created/dt=YYYY-MM-DD/lead_id=<LEAD_ID>/crm_event_<LEAD_ID>.json
            if not key.startswith(f"{RAW_PREFIX}/"):
                continue

            parts = key.split("/")
            if len(parts) < 5 or parts[0] != "crm" or parts[1] != "lead_created":
                continue

            day     = parts[2].split("=", 1)[1]     # dt=YYYY-MM-DD
            lead_id = parts[3].split("=", 1)[1]     # lead_id=<LEAD_ID>

            # Load raw event JSON
            raw  = _read_json_from_s3(bucket, key)
            data = raw.get("event", {}).get("data", {})

            owner_payload = {}
            lookup_status = "skipped" if SKIP_OWNER_LOOKUP else "ok"

            if not SKIP_OWNER_LOOKUP:
                owner_url = f"{OWNER_BASE}/{lead_id}.json"
                try:
                    owner_payload = fetch_owner_json(owner_url)
                except Exception as e:
                    kind = classify_lookup_error(e)
                    if kind == "permanent":
                        # Write failure artifact and proceed WITHOUT raising (consume message)
                        _write_error_artifact(
                            day, lead_id,
                            reason=f"permanent:{type(e).__name__}",
                            extra={"detail": str(e)}
                        )
                        lookup_status = "permanent_failed"
                        owner_payload = {}
                    else:
                        # transient/unknown: raise so SQS retries and eventually DLQs
                        raise

            enriched = {
                "lead_id": lead_id,
                "display_name": data.get("display_name"),
                "status_label": data.get("status_label"),
                "date_created": data.get("date_created"),
                "lead_email": owner_payload.get("lead_email"),
                "lead_owner": owner_payload.get("lead_owner"),
                "funnel": owner_payload.get("funnel"),
                "assignee": owner_payload.get("lead_owner"),  # mirrors owner if present
                "enriched_at": _now_iso(),
                "owner_lookup_status": lookup_status,
            }

            out_key = f"{CURATED_PREFIX}/dt={day}/lead_id={lead_id}/lead_{lead_id}.json"
            _write_json_to_s3(CURATED_BUCKET, out_key, enriched)

            # --- Slack Notification ---
            hook = _slack_url()
            if hook:
                msg = {
                    "text": "New Lead Alert",
                    "blocks": [
                        {"type": "header","text": {"type": "plain_text","text": "New Lead Enriched"}},
                        {"type": "section","fields": [
                            {"type": "mrkdwn","text": f"*Name:*\n{enriched.get('display_name') or 'N/A'}"},
                            {"type": "mrkdwn","text": f"*Lead ID:*\n{lead_id}"},
                            {"type": "mrkdwn","text": f"*Created:*\n{enriched.get('date_created') or 'N/A'}"},
                            {"type": "mrkdwn","text": f"*Label:*\n{enriched.get('status_label') or 'N/A'}"},
                            {"type": "mrkdwn","text": f"*Email:*\n{enriched.get('lead_email') or 'N/A'}"},
                            {"type": "mrkdwn","text": f"*Lead Owner:*\n{enriched.get('lead_owner') or 'Unassigned'}"},
                            {"type": "mrkdwn","text": f"*Funnel:*\n{enriched.get('funnel') or 'N/A'}"},
                        ]},
                        {"type": "context","elements":[{"type":"mrkdwn","text": f"Enriched at {enriched['enriched_at']}"}]},
                    ],
                }
                status, body = _post_slack(hook, msg)
                print(f"[slack] post status={status} body={body[:200]}")

        # Success → SQS deletes the messages we processed in this batch
        return {"ok": True}
