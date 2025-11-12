#!/bin/bash

# Load environment variables from .env file
set -a
source .env
set +a

echo "=========================================="
echo "CRM Leads Infrastructure Deployment"
echo "=========================================="
echo ""

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

echo "1. Creating S3 Bucket for lead data storage..."
aws s3 mb s3://${S3_BUCKET_NAME} --region ${AWS_REGION} 2>/dev/null || echo "Bucket already exists or error creating bucket"
aws s3api put-bucket-versioning --bucket ${S3_BUCKET_NAME} --versioning-configuration Status=Enabled --region ${AWS_REGION}
echo "✓ S3 Bucket configured"
echo ""

echo "2. Creating SQS Queue with 10-minute delay..."
SQS_QUEUE_URL=$(aws sqs create-queue \
    --queue-name ${SQS_QUEUE_NAME} \
    --attributes DelaySeconds=0,MessageRetentionPeriod=1209600,VisibilityTimeout=300 \
    --region ${AWS_REGION} \
    --output text --query 'QueueUrl' 2>/dev/null)

if [ -z "$SQS_QUEUE_URL" ]; then
    SQS_QUEUE_URL=$(aws sqs get-queue-url --queue-name ${SQS_QUEUE_NAME} --region ${AWS_REGION} --output text --query 'QueueUrl')
fi

echo "✓ SQS Queue created: $SQS_QUEUE_URL"
echo ""

echo "3. Creating IAM Role for Lambda functions..."
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}'

# Create IAM role
aws iam create-role \
    --role-name ${LAMBDA_EXECUTION_ROLE_NAME} \
    --assume-role-policy-document "$TRUST_POLICY" \
    --region ${AWS_REGION} 2>/dev/null || echo "Role already exists"

# Attach policies
aws iam attach-role-policy \
    --role-name ${LAMBDA_EXECUTION_ROLE_NAME} \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
    --region ${AWS_REGION}

# Create custom policy for S3 and SQS access
CUSTOM_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::'${S3_BUCKET_NAME}'",
        "arn:aws:s3:::'${S3_BUCKET_NAME}'/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:'${AWS_REGION}':'${AWS_ACCOUNT_ID}':'${SQS_QUEUE_NAME}'"
    }
  ]
}'

POLICY_ARN=$(aws iam create-policy \
    --policy-name ${LAMBDA_EXECUTION_ROLE_NAME}-policy \
    --policy-document "$CUSTOM_POLICY" \
    --region ${AWS_REGION} \
    --output text --query 'Policy.Arn' 2>/dev/null)

if [ -z "$POLICY_ARN" ]; then
    POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${LAMBDA_EXECUTION_ROLE_NAME}-policy"
fi

aws iam attach-role-policy \
    --role-name ${LAMBDA_EXECUTION_ROLE_NAME} \
    --policy-arn $POLICY_ARN \
    --region ${AWS_REGION}

echo "✓ IAM Role and policies configured"
echo ""

# Wait for IAM role to propagate
echo "Waiting 10 seconds for IAM role to propagate..."
sleep 10

echo "=========================================="
echo "Infrastructure deployment completed!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run ./scripts/deploy-lambdas.sh to deploy Lambda functions"
echo "2. Run ./scripts/deploy-api-gateway.sh to set up API Gateway"
echo ""
