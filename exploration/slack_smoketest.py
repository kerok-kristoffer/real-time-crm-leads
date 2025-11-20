import os, json, boto3, requests

SLACK_SECRET_NAME = os.getenv("SLACK_SECRET_NAME")  # either a full URL or a secret name

_cached_url = None
def _slack_url():
    global _cached_url
    if _cached_url:
        return _cached_url

    sm = boto3.client("secretsmanager")
    resp = sm.get_secret_value(SecretId=SLACK_SECRET_NAME)
    secret = json.loads(resp["SecretString"])
    _cached_url = secret["url"]
    return _cached_url

def lambda_handler(event, context):
    url = _slack_url()
    payload = {
        "text": "Slack smoke-test from Lambda",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "Slack Smoke Test"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": "*Source:*\nslack-smoketest Lambda"},
                {"type": "mrkdwn", "text": "*Env var:* `SLACK_SECRET_NAME`"},
            ]}
        ],
    }

    r = requests.post(url, json=payload, timeout=8)
    return {"status_code": r.status_code, "text": r.text[:200]}
