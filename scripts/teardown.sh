#!/bin/bash

# Load environment variables from .env file
set -a
source .env
set +a

echo "=========================================="
echo "CRM Leads Infrastructure Teardown"
echo "=========================================="
echo ""
echo "WARNING: This will delete all resources!"
read -p "Are you sure you want to continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Teardown cancelled."
    exit 0
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found."
    exit 1
fi

API_ID=$(aws apigateway get-rest-apis --region ${AWS_REGION} --query "items[?name=='${API_GATEWAY_NAME}'].id" --output text)

echo "1. Deleting API Gateway..."
if [ ! -z "$API_ID" ]; then
    aws apigateway delete-rest-api --rest-api-id ${API_ID} --region ${AWS_REGION}
    echo "✓ API Gateway deleted"
else
    echo "API Gateway not found"
fi
echo ""

echo "2. Deleting Lambda event source mapping..."
MAPPING_UUID=$(aws lambda list-event-source-mappings \
    --function-name ${REFINEMENT_LAMBDA_NAME} \
    --region ${AWS_REGION} \
    --query 'EventSourceMappings[0].UUID' \
    --output text)

if [ ! -z "$MAPPING_UUID" ] && [ "$MAPPING_UUID" != "None" ]; then
    aws lambda delete-event-source-mapping --uuid ${MAPPING_UUID} --region ${AWS_REGION}
    echo "✓ Event source mapping deleted"
else
    echo "No event source mapping found"
fi
echo ""

echo "3. Deleting Lambda functions..."
aws lambda delete-function --function-name ${CAPTURE_LAMBDA_NAME} --region ${AWS_REGION} 2>/dev/null && echo "✓ Capture Lambda deleted" || echo "Capture Lambda not found"
aws lambda delete-function --function-name ${REFINEMENT_LAMBDA_NAME} --region ${AWS_REGION} 2>/dev/null && echo "✓ Refinement Lambda deleted" || echo "Refinement Lambda not found"
echo ""

echo "4. Deleting SQS Queue..."
SQS_QUEUE_URL=$(aws sqs get-queue-url --queue-name ${SQS_QUEUE_NAME} --region ${AWS_REGION} --output text --query 'QueueUrl' 2>/dev/null)
if [ ! -z "$SQS_QUEUE_URL" ]; then
    aws sqs delete-queue --queue-url ${SQS_QUEUE_URL} --region ${AWS_REGION}
    echo "✓ SQS Queue deleted"
else
    echo "SQS Queue not found"
fi
echo ""

echo "5. Emptying and deleting S3 Bucket..."
aws s3 rm s3://${S3_BUCKET_NAME} --recursive --region ${AWS_REGION} 2>/dev/null
aws s3 rb s3://${S3_BUCKET_NAME} --region ${AWS_REGION} 2>/dev/null && echo "✓ S3 Bucket deleted" || echo "S3 Bucket not found or not empty"
echo ""

echo "6. Detaching policies and deleting IAM Role..."
POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${LAMBDA_EXECUTION_ROLE_NAME}-policy"

aws iam detach-role-policy \
    --role-name ${LAMBDA_EXECUTION_ROLE_NAME} \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
    --region ${AWS_REGION} 2>/dev/null

aws iam detach-role-policy \
    --role-name ${LAMBDA_EXECUTION_ROLE_NAME} \
    --policy-arn ${POLICY_ARN} \
    --region ${AWS_REGION} 2>/dev/null

aws iam delete-role \
    --role-name ${LAMBDA_EXECUTION_ROLE_NAME} \
    --region ${AWS_REGION} 2>/dev/null && echo "✓ IAM Role deleted" || echo "IAM Role not found"

aws iam delete-policy \
    --policy-arn ${POLICY_ARN} \
    --region ${AWS_REGION} 2>/dev/null && echo "✓ IAM Policy deleted" || echo "IAM Policy not found"

echo ""
echo "=========================================="
echo "Teardown completed!"
echo "=========================================="
echo ""
