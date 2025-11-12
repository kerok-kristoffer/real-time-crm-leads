#!/bin/bash

# Script to test the webhook endpoint with sample data
# Usage: ./scripts/test-webhook.sh <webhook-url>

if [ -z "$1" ]; then
    echo "Usage: ./scripts/test-webhook.sh <webhook-url>"
    echo ""
    echo "Example:"
    echo "  ./scripts/test-webhook.sh https://abc123.execute-api.us-east-1.amazonaws.com/prod/webhook"
    exit 1
fi

WEBHOOK_URL=$1

echo "=========================================="
echo "Testing CRM Webhook Endpoint"
echo "=========================================="
echo ""
echo "Webhook URL: $WEBHOOK_URL"
echo ""

# Test 1: Basic lead
echo "Test 1: Sending basic lead data..."
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "+1-555-0123",
    "company": "Example Corp",
    "source": "Website Form",
    "campaign": "Q4 2024",
    "lead_score": 85,
    "owner": "sales@example.com"
  }')

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✓ Test 1 PASSED (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
else
    echo "✗ Test 1 FAILED (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
fi
echo ""

# Test 2: Minimal lead (required fields only)
echo "Test 2: Sending minimal lead data..."
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Jane Smith",
    "email": "jane@test.com"
  }')

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✓ Test 2 PASSED (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
else
    echo "✗ Test 2 FAILED (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
fi
echo ""

# Test 3: Lead with special characters
echo "Test 3: Sending lead with special characters..."
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "María García-López",
    "email": "maria.garcia@empresa.es",
    "phone": "+34 91 123 4567",
    "company": "Café & Restaurant \"La Plaza\"",
    "source": "Email Campaign"
  }')

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✓ Test 3 PASSED (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
else
    echo "✗ Test 3 FAILED (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
fi
echo ""

echo "=========================================="
echo "Testing Complete!"
echo "=========================================="
echo ""
echo "Note: Leads will be processed and sent to Slack after 10 minutes."
echo "Check CloudWatch Logs to monitor processing:"
echo "  aws logs tail /aws/lambda/crm-leads-capture --follow"
echo "  aws logs tail /aws/lambda/crm-leads-refinement --follow"
echo ""
