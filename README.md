# Real-Time CRM Leads Automation

This project automates the capture of newly created leads via CRM webhooks, implements a 10-minute buffer period for data enrichment, and notifies the sales team via Slack with cleaned and refined lead information.

## Architecture

The system uses AWS serverless components to create a robust, scalable lead processing pipeline:

```
CRM Webhook → API Gateway → Capture Lambda → S3 (Raw Data)
                                ↓
                            SQS Queue (10 min delay)
                                ↓
                          Refinement Lambda → S3 (Refined Data) → Slack Notification
```

### Components

1. **API Gateway**: REST API endpoint that receives webhook POST requests from the CRM
2. **Capture Lambda**: Processes incoming webhooks, stores raw data in S3, and queues for delayed processing
3. **SQS Queue**: Provides 10-minute delay between capture and refinement
4. **Refinement Lambda**: Cleans/enriches data, stores refined version, and sends Slack notification
5. **S3 Bucket**: Stores both raw and refined lead data in JSON format

## Project Structure

```
.
├── lambdas/
│   ├── capture/
│   │   ├── lambda_function.py      # Webhook capture handler
│   │   └── requirements.txt
│   └── refinement/
│       ├── lambda_function.py      # Data refinement and Slack notification
│       └── requirements.txt
├── scripts/
│   ├── deploy-infrastructure.sh    # Creates S3, SQS, IAM resources
│   ├── deploy-lambdas.sh           # Deploys Lambda functions
│   ├── deploy-api-gateway.sh       # Sets up API Gateway
│   └── teardown.sh                 # Removes all AWS resources
├── .env.example                    # Environment variables template
└── README.md
```

## Setup

### Prerequisites

- AWS CLI installed and configured with appropriate credentials
- Python 3.11 or later
- Bash shell (for deployment scripts)
- Active AWS account with permissions to create Lambda, S3, SQS, IAM, and API Gateway resources

### Configuration

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Edit `.env` and configure your settings:
```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# S3 Bucket (must be globally unique)
S3_BUCKET_NAME=your-unique-crm-leads-bucket

# SQS Queue
SQS_QUEUE_NAME=crm-leads-processing-queue

# Lambda Functions
CAPTURE_LAMBDA_NAME=crm-leads-capture
REFINEMENT_LAMBDA_NAME=crm-leads-refinement

# API Gateway
API_GATEWAY_NAME=crm-webhook-api

# Slack Webhook URL (get from Slack App settings)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# IAM Role
LAMBDA_EXECUTION_ROLE_NAME=crm-leads-lambda-role
```

### Deployment

Deploy the entire infrastructure in three steps:

#### Step 1: Deploy Infrastructure (S3, SQS, IAM)
```bash
./scripts/deploy-infrastructure.sh
```

This creates:
- S3 bucket with versioning enabled
- SQS queue configured for delayed processing
- IAM role and policies for Lambda functions

#### Step 2: Deploy Lambda Functions
```bash
./scripts/deploy-lambdas.sh
```

This:
- Packages both Lambda functions with dependencies
- Deploys them to AWS
- Configures environment variables
- Sets up SQS trigger for refinement Lambda

#### Step 3: Deploy API Gateway
```bash
./scripts/deploy-api-gateway.sh
```

This:
- Creates REST API
- Configures POST endpoint at `/webhook`
- Links to capture Lambda
- Deploys to production stage

After deployment, you'll receive a webhook URL like:
```
https://{api-id}.execute-api.{region}.amazonaws.com/prod/webhook
```

## Usage

### Configure Your CRM

Point your CRM webhook to the API Gateway URL. The webhook should send POST requests with JSON payloads containing lead data.

### Expected Webhook Format

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+1-555-0123",
  "company": "Example Inc",
  "source": "Website Form",
  "campaign": "Q4 Campaign",
  "lead_score": 85,
  "owner": "sales@example.com"
}
```

### Testing the Webhook

```bash
curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/prod/webhook \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Jane Smith",
    "email": "jane@test.com",
    "phone": "555-1234",
    "company": "Test Corp",
    "source": "Demo Request",
    "owner": "sales@example.com"
  }'
```

### Data Flow

1. **Immediate (0 seconds)**: Webhook received → Raw data stored in S3 → Message sent to SQS
2. **After 10 minutes**: SQS triggers refinement → Data cleaned → Refined data stored → Slack notification sent

### S3 Storage Structure

```
s3://your-bucket/
├── raw/
│   └── YYYY/MM/DD/
│       └── {lead-id}.json
└── refined/
    └── YYYY/MM/DD/
        └── {lead-id}.json
```

## Monitoring

### CloudWatch Logs

View logs for each Lambda function:
```bash
# Capture Lambda logs
aws logs tail /aws/lambda/crm-leads-capture --follow

# Refinement Lambda logs
aws logs tail /aws/lambda/crm-leads-refinement --follow
```

### Check SQS Queue

```bash
aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name crm-leads-processing-queue --query 'QueueUrl' --output text) \
  --attribute-names ApproximateNumberOfMessages
```

### List S3 Objects

```bash
aws s3 ls s3://your-bucket/raw/ --recursive
aws s3 ls s3://your-bucket/refined/ --recursive
```

## Cleanup

To remove all AWS resources:

```bash
./scripts/teardown.sh
```

⚠️ **Warning**: This will permanently delete all resources including stored lead data in S3.

## Customization

### Adjust Delay Time

To change the 10-minute delay, modify the `DelaySeconds` parameter in `lambdas/capture/lambda_function.py`:

```python
sqs_client.send_message(
    QueueUrl=SQS_QUEUE_URL,
    MessageBody=json.dumps(sqs_message),
    DelaySeconds=600  # Change this value (max 900 seconds = 15 minutes)
)
```

### Customize Data Cleaning

Edit the `refine_lead_data()` function in `lambdas/refinement/lambda_function.py` to add your own data cleaning logic.

### Customize Slack Notifications

Edit the `send_slack_notification()` function in `lambdas/refinement/lambda_function.py` to modify the message format.

## Cost Estimation

This architecture uses serverless components with pay-per-use pricing:

- **API Gateway**: $3.50 per million requests
- **Lambda**: First 1M requests free, then $0.20 per 1M requests
- **SQS**: First 1M requests free, then $0.40 per 1M requests
- **S3**: $0.023 per GB/month storage

Example: 10,000 leads/month ≈ $0.50-$1.00/month

## Security Considerations

- ✅ `.env` file excluded from git via `.gitignore`
- ✅ Secrets stored as environment variables
- ✅ IAM roles follow least-privilege principle
- ✅ S3 bucket versioning enabled
- 🔒 Consider adding API Gateway authentication for production
- 🔒 Consider encrypting S3 bucket with KMS

## Troubleshooting

### Lambda Permission Errors
If you see "Access Denied" errors, wait a few minutes for IAM roles to propagate, then redeploy.

### SQS Messages Not Processing
Check that the event source mapping is active:
```bash
aws lambda list-event-source-mappings --function-name crm-leads-refinement
```

### Slack Notifications Not Sending
Verify your `SLACK_WEBHOOK_URL` in `.env` is correct and the Slack app has permission to post to the channel.

## Contributing

Feel free to open issues or submit pull requests for improvements!

## License

MIT License - See LICENSE file for details
