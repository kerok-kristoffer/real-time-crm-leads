import json, os, datetime, boto3

s3 = boto3.client("s3")
RAW_BUCKET = os.environ["RAW_BUCKET"]
RAW_PREFIX = os.environ.get("RAW_PREFIX", "crm/lead_created")

def _iso_now():
    return datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()

def lambda_handler(event, context):
    # API Gateway HTTP API will pass body as a JSON string
    try:
        body = json.loads(event.get("body") or "{}")
    except Exception:
        return {"statusCode": 400, "body": json.dumps({"error": "invalid JSON body"})}

    # Defensive extraction (Close puts lead_id under event.lead_id)
    lead_id = (
        body.get("event", {}).get("lead_id")
        or body.get("lead_id")
        or body.get("event", {}).get("object_id")
    )
    if not lead_id:
        return {"statusCode": 400, "body": json.dumps({"error": "missing lead_id"})}

    # Stamp a couple of fields we’ll use later
    envelope = {
        **body,
        "ingested_at": _iso_now(),
        "assignee": None,
        "enrichment_status": "pending"
    }

    # Partition by day and use deterministic key (idempotent)
    day = envelope.get("event", {}).get("date_created", "")[:10]
    if not day:
        day = datetime.date.today().isoformat()

    key = f"{RAW_PREFIX}/dt={day}/lead_id={lead_id}/crm_event_{lead_id}.json"
    s3.put_object(
        Bucket=RAW_BUCKET,
        Key=key,
        Body=json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )

    return {"statusCode": 200, "body": json.dumps({"ok": True, "lead_id": lead_id})}
