#!/bin/bash

# Load environment variables from .env file
set -a
source .env
set +a

echo "=========================================="
echo "Lambda Functions Deployment"
echo "=========================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Get SQS Queue URL
SQS_QUEUE_URL=$(aws sqs get-queue-url --queue-name ${SQS_QUEUE_NAME} --region ${AWS_REGION} --output text --query 'QueueUrl')
ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${LAMBDA_EXECUTION_ROLE_NAME}"

echo "1. Packaging Capture Lambda function..."
cd lambdas/capture
if [ -f requirements.txt ]; then
    pip install -r requirements.txt -t ./ --quiet
fi
zip -r capture-lambda.zip . -x "*.pyc" "__pycache__/*" "*.zip" > /dev/null
echo "✓ Capture Lambda packaged"
echo ""

echo "2. Deploying Capture Lambda function..."
CAPTURE_LAMBDA_ARN=$(aws lambda create-function \
    --function-name ${CAPTURE_LAMBDA_NAME} \
    --runtime python3.11 \
    --role ${ROLE_ARN} \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://capture-lambda.zip \
    --timeout 30 \
    --memory-size 256 \
    --environment Variables="{S3_BUCKET=${S3_BUCKET_NAME},SQS_QUEUE_URL=${SQS_QUEUE_URL}}" \
    --region ${AWS_REGION} \
    --output text --query 'FunctionArn' 2>/dev/null)

if [ -z "$CAPTURE_LAMBDA_ARN" ]; then
    echo "Function exists, updating..."
    aws lambda update-function-code \
        --function-name ${CAPTURE_LAMBDA_NAME} \
        --zip-file fileb://capture-lambda.zip \
        --region ${AWS_REGION} > /dev/null
    
    aws lambda update-function-configuration \
        --function-name ${CAPTURE_LAMBDA_NAME} \
        --environment Variables="{S3_BUCKET=${S3_BUCKET_NAME},SQS_QUEUE_URL=${SQS_QUEUE_URL}}" \
        --region ${AWS_REGION} > /dev/null
    
    CAPTURE_LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${CAPTURE_LAMBDA_NAME}"
fi

echo "✓ Capture Lambda deployed: $CAPTURE_LAMBDA_ARN"
rm capture-lambda.zip
cd ../..
echo ""

echo "3. Packaging Refinement Lambda function..."
cd lambdas/refinement
if [ -f requirements.txt ]; then
    pip install -r requirements.txt -t ./ --quiet
fi
zip -r refinement-lambda.zip . -x "*.pyc" "__pycache__/*" "*.zip" > /dev/null
echo "✓ Refinement Lambda packaged"
echo ""

echo "4. Deploying Refinement Lambda function..."
REFINEMENT_LAMBDA_ARN=$(aws lambda create-function \
    --function-name ${REFINEMENT_LAMBDA_NAME} \
    --runtime python3.11 \
    --role ${ROLE_ARN} \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://refinement-lambda.zip \
    --timeout 60 \
    --memory-size 512 \
    --environment Variables="{S3_BUCKET=${S3_BUCKET_NAME},SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}}" \
    --region ${AWS_REGION} \
    --output text --query 'FunctionArn' 2>/dev/null)

if [ -z "$REFINEMENT_LAMBDA_ARN" ]; then
    echo "Function exists, updating..."
    aws lambda update-function-code \
        --function-name ${REFINEMENT_LAMBDA_NAME} \
        --zip-file fileb://refinement-lambda.zip \
        --region ${AWS_REGION} > /dev/null
    
    aws lambda update-function-configuration \
        --function-name ${REFINEMENT_LAMBDA_NAME} \
        --environment Variables="{S3_BUCKET=${S3_BUCKET_NAME},SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}}" \
        --region ${AWS_REGION} > /dev/null
    
    REFINEMENT_LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${REFINEMENT_LAMBDA_NAME}"
fi

echo "✓ Refinement Lambda deployed: $REFINEMENT_LAMBDA_ARN"
rm refinement-lambda.zip
cd ../..
echo ""

echo "5. Setting up SQS trigger for Refinement Lambda..."
# Get SQS Queue ARN
SQS_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:${SQS_QUEUE_NAME}"

# Create event source mapping
aws lambda create-event-source-mapping \
    --function-name ${REFINEMENT_LAMBDA_NAME} \
    --event-source-arn ${SQS_QUEUE_ARN} \
    --batch-size 10 \
    --region ${AWS_REGION} 2>/dev/null || echo "Event source mapping already exists"

echo "✓ SQS trigger configured"
echo ""

echo "=========================================="
echo "Lambda deployment completed!"
echo "=========================================="
echo ""
echo "Deployed functions:"
echo "  - Capture: ${CAPTURE_LAMBDA_ARN}"
echo "  - Refinement: ${REFINEMENT_LAMBDA_ARN}"
echo ""
