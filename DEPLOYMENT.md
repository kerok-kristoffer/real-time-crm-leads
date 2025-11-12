# Deployment Guide

This guide provides step-by-step instructions for deploying the Real-Time CRM Leads Automation system.

## Prerequisites Checklist

Before starting deployment, ensure you have:

- [ ] AWS CLI installed (`aws --version` should work)
- [ ] AWS credentials configured (`aws sts get-caller-identity` should work)
- [ ] Python 3.11+ installed
- [ ] `pip` package manager available
- [ ] Sufficient AWS permissions (Lambda, S3, SQS, IAM, API Gateway)
- [ ] A Slack workspace with webhook URL created

## Initial Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd real-time-crm-leads
```

### 2. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit the file with your values
nano .env  # or use your preferred editor
```

**Required Configuration:**

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_REGION` | AWS region to deploy to | `us-east-1` |
| `AWS_ACCOUNT_ID` | Your 12-digit AWS account ID | `123456789012` |
| `S3_BUCKET_NAME` | Globally unique bucket name | `mycompany-crm-leads-2024` |
| `SQS_QUEUE_NAME` | SQS queue name | `crm-leads-processing-queue` |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | `https://hooks.slack.com/...` |

**How to find your AWS Account ID:**
```bash
aws sts get-caller-identity --query Account --output text
```

**How to create a Slack Webhook:**
1. Go to https://api.slack.com/apps
2. Create a new app or select existing
3. Enable "Incoming Webhooks"
4. Add webhook to workspace
5. Copy the webhook URL

### 3. Verify AWS Permissions

Test that you have necessary permissions:

```bash
# Test S3 access
aws s3 ls

# Test Lambda access
aws lambda list-functions --region us-east-1

# Test IAM access
aws iam list-roles --max-items 1
```

## Deployment Steps

### Step 1: Deploy Infrastructure

This step creates the foundational AWS resources.

```bash
./scripts/deploy-infrastructure.sh
```

**What this does:**
- Creates S3 bucket with versioning
- Creates SQS queue
- Creates IAM role with necessary policies
- Waits for IAM propagation

**Expected output:**
```
==========================================
CRM Leads Infrastructure Deployment
==========================================

1. Creating S3 Bucket for lead data storage...
✓ S3 Bucket configured

2. Creating SQS Queue with 10-minute delay...
✓ SQS Queue created: https://sqs.us-east-1.amazonaws.com/...

3. Creating IAM Role for Lambda functions...
✓ IAM Role and policies configured

Infrastructure deployment completed!
```

**Troubleshooting:**
- If bucket creation fails, the bucket name might already exist globally
- If IAM role creation fails, you might lack IAM permissions
- Wait at least 10 seconds before proceeding to next step

### Step 2: Deploy Lambda Functions

This step packages and deploys both Lambda functions.

```bash
./scripts/deploy-lambdas.sh
```

**What this does:**
- Installs Python dependencies
- Packages Lambda functions as ZIP files
- Deploys to AWS Lambda
- Configures environment variables
- Sets up SQS trigger for refinement Lambda

**Expected output:**
```
==========================================
Lambda Functions Deployment
==========================================

1. Packaging Capture Lambda function...
✓ Capture Lambda packaged

2. Deploying Capture Lambda function...
✓ Capture Lambda deployed: arn:aws:lambda:...

3. Packaging Refinement Lambda function...
✓ Refinement Lambda packaged

4. Deploying Refinement Lambda function...
✓ Refinement Lambda deployed: arn:aws:lambda:...

5. Setting up SQS trigger for Refinement Lambda...
✓ SQS trigger configured
```

**Troubleshooting:**
- If deployment fails due to role not found, wait longer for IAM propagation
- If you see "InvalidParameterValueException", verify your AWS_ACCOUNT_ID is correct
- Check CloudWatch Logs for Lambda errors

### Step 3: Deploy API Gateway

This step creates the webhook endpoint.

```bash
./scripts/deploy-api-gateway.sh
```

**What this does:**
- Creates REST API
- Creates `/webhook` resource
- Configures POST method
- Links to Capture Lambda
- Grants API Gateway invoke permissions
- Deploys to production stage

**Expected output:**
```
==========================================
API Gateway Deployment
==========================================

...

Webhook URL:
https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/webhook
```

**⚠️ IMPORTANT:** Copy and save your webhook URL!

## Verification

### Test the Webhook

```bash
# Replace {webhook-url} with your actual URL
curl -X POST {webhook-url} \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Test Lead",
    "email": "test@example.com",
    "phone": "555-1234",
    "company": "Test Company",
    "source": "Manual Test"
  }'
```

**Expected response:**
```json
{
  "message": "Lead captured successfully",
  "lead_id": "a1b2c3d4-..."
}
```

### Check Capture Lambda Logs

```bash
aws logs tail /aws/lambda/crm-leads-capture --follow --region us-east-1
```

### Verify Data in S3

```bash
aws s3 ls s3://${S3_BUCKET_NAME}/raw/ --recursive
```

You should see a JSON file with your test lead.

### Check SQS Queue

```bash
aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name crm-leads-processing-queue --query 'QueueUrl' --output text --region us-east-1) \
  --attribute-names ApproximateNumberOfMessages \
  --region us-east-1
```

Should show 1 message (if within 10 minutes of sending test).

### Wait for Slack Notification

After 10 minutes, you should:
1. See the message processed in SQS
2. Find refined data in S3: `s3://${S3_BUCKET_NAME}/refined/`
3. Receive a Slack notification in your configured channel

### Check Refinement Lambda Logs

```bash
aws logs tail /aws/lambda/crm-leads-refinement --follow --region us-east-1
```

## Post-Deployment

### Configure Your CRM

Add the webhook URL to your CRM system:

**Salesforce:**
1. Setup → Workflow & Approvals → Workflow Rules
2. Create new rule for Lead creation
3. Add Outbound Message action with your webhook URL

**HubSpot:**
1. Settings → Integrations → Webhooks
2. Create webhook subscription for "contact.creation"
3. Add your webhook URL

**Other CRMs:**
Consult your CRM's documentation for webhook/API configuration.

### Monitor the System

1. **CloudWatch Dashboards**: Consider creating a dashboard
2. **CloudWatch Alarms**: Set up alarms for Lambda errors
3. **S3 Lifecycle Rules**: Configure data retention policies
4. **Cost Monitoring**: Set up billing alerts

### Security Hardening (Production)

Before going to production, consider:

1. **API Authentication**: Add API key or JWT validation
```bash
aws apigateway create-api-key --name crm-webhook-key --enabled
```

2. **S3 Encryption**: Enable server-side encryption
```bash
aws s3api put-bucket-encryption \
  --bucket ${S3_BUCKET_NAME} \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'
```

3. **VPC Integration**: Deploy Lambdas in VPC for network isolation

4. **Secrets Manager**: Move Slack webhook to AWS Secrets Manager
```bash
aws secretsmanager create-secret \
  --name crm-leads-slack-webhook \
  --secret-string "${SLACK_WEBHOOK_URL}"
```

## Updating the System

### Update Lambda Code

After modifying Lambda function code:

```bash
./scripts/deploy-lambdas.sh
```

This will update existing functions without recreating resources.

### Update Configuration

To change environment variables:

1. Update `.env` file
2. Run `./scripts/deploy-lambdas.sh` to apply changes

Or update directly:
```bash
aws lambda update-function-configuration \
  --function-name crm-leads-capture \
  --environment Variables="{S3_BUCKET=new-bucket,SQS_QUEUE_URL=new-url}"
```

## Rollback

If something goes wrong, you can:

### Rollback Lambda Function

```bash
# List versions
aws lambda list-versions-by-function --function-name crm-leads-capture

# Rollback to previous version
aws lambda update-alias \
  --function-name crm-leads-capture \
  --name PROD \
  --function-version 1
```

### Complete Teardown

To remove everything and start fresh:

```bash
./scripts/teardown.sh
```

⚠️ **Warning**: This permanently deletes all data!

## Common Issues

### Issue: "Bucket already exists"
**Solution**: Change `S3_BUCKET_NAME` in `.env` to something globally unique

### Issue: "Access Denied" when creating IAM role
**Solution**: Ensure your AWS user has IAM permissions or use an administrator account

### Issue: Lambda timeout errors
**Solution**: Increase timeout in deploy-lambdas.sh or via console

### Issue: SQS messages not being processed
**Solution**: Check event source mapping is active:
```bash
aws lambda list-event-source-mappings --function-name crm-leads-refinement
```

### Issue: Slack notifications not working
**Solution**: 
1. Verify webhook URL is correct
2. Check refinement Lambda logs for errors
3. Test webhook manually with curl

## Support

For issues or questions:
1. Check CloudWatch Logs for error details
2. Review this deployment guide
3. Open an issue in the repository
4. Contact your AWS support if needed

## Next Steps

- [ ] Configure your CRM webhook
- [ ] Set up CloudWatch alarms
- [ ] Configure S3 lifecycle policies
- [ ] Implement API authentication
- [ ] Set up monitoring dashboard
- [ ] Document your custom data fields
- [ ] Train team on monitoring procedures
