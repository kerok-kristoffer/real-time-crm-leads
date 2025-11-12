#!/bin/bash

# Load environment variables from .env file
set -a
source .env
set +a

echo "=========================================="
echo "API Gateway Deployment"
echo "=========================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

CAPTURE_LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${CAPTURE_LAMBDA_NAME}"

echo "1. Creating REST API..."
API_ID=$(aws apigateway create-rest-api \
    --name ${API_GATEWAY_NAME} \
    --description "Webhook endpoint for CRM leads capture" \
    --region ${AWS_REGION} \
    --output text --query 'id' 2>/dev/null)

if [ -z "$API_ID" ]; then
    echo "API might already exist, searching..."
    API_ID=$(aws apigateway get-rest-apis --region ${AWS_REGION} --query "items[?name=='${API_GATEWAY_NAME}'].id" --output text)
fi

echo "✓ API created/found: $API_ID"
echo ""

echo "2. Getting root resource..."
ROOT_RESOURCE_ID=$(aws apigateway get-resources \
    --rest-api-id ${API_ID} \
    --region ${AWS_REGION} \
    --query 'items[?path==`/`].id' \
    --output text)

echo "✓ Root resource: $ROOT_RESOURCE_ID"
echo ""

echo "3. Creating /webhook resource..."
WEBHOOK_RESOURCE_ID=$(aws apigateway create-resource \
    --rest-api-id ${API_ID} \
    --parent-id ${ROOT_RESOURCE_ID} \
    --path-part webhook \
    --region ${AWS_REGION} \
    --output text --query 'id' 2>/dev/null)

if [ -z "$WEBHOOK_RESOURCE_ID" ]; then
    WEBHOOK_RESOURCE_ID=$(aws apigateway get-resources \
        --rest-api-id ${API_ID} \
        --region ${AWS_REGION} \
        --query "items[?path=='/webhook'].id" \
        --output text)
fi

echo "✓ Webhook resource: $WEBHOOK_RESOURCE_ID"
echo ""

echo "4. Creating POST method..."
aws apigateway put-method \
    --rest-api-id ${API_ID} \
    --resource-id ${WEBHOOK_RESOURCE_ID} \
    --http-method POST \
    --authorization-type NONE \
    --region ${AWS_REGION} 2>/dev/null || echo "Method already exists"

echo "✓ POST method configured"
echo ""

echo "5. Setting up Lambda integration..."
aws apigateway put-integration \
    --rest-api-id ${API_ID} \
    --resource-id ${WEBHOOK_RESOURCE_ID} \
    --http-method POST \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${CAPTURE_LAMBDA_ARN}/invocations \
    --region ${AWS_REGION} 2>/dev/null || echo "Integration already exists"

echo "✓ Lambda integration configured"
echo ""

echo "6. Granting API Gateway permission to invoke Lambda..."
aws lambda add-permission \
    --function-name ${CAPTURE_LAMBDA_NAME} \
    --statement-id apigateway-webhook-invoke \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${API_ID}/*/POST/webhook" \
    --region ${AWS_REGION} 2>/dev/null || echo "Permission already exists"

echo "✓ Lambda permission granted"
echo ""

echo "7. Deploying API..."
aws apigateway create-deployment \
    --rest-api-id ${API_ID} \
    --stage-name prod \
    --region ${AWS_REGION} > /dev/null

echo "✓ API deployed to prod stage"
echo ""

echo "=========================================="
echo "API Gateway deployment completed!"
echo "=========================================="
echo ""
echo "Webhook URL:"
echo "https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/webhook"
echo ""
echo "Test the webhook with:"
echo "curl -X POST https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/webhook \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"name\":\"John Doe\",\"email\":\"john@example.com\",\"company\":\"Example Inc\"}'"
echo ""
