# Quick Start Guide

Get your CRM leads automation system up and running in under 10 minutes!

## Prerequisites

- AWS CLI configured with credentials
- Python 3.11+
- Slack webhook URL

## Setup (5 minutes)

### 1. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your values
nano .env
```

**Minimum Required Configuration:**
```bash
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012  # Get with: aws sts get-caller-identity --query Account --output text
S3_BUCKET_NAME=my-company-crm-leads-2024  # Must be globally unique
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 2. Deploy Infrastructure (2 minutes)

```bash
# Deploy S3, SQS, IAM roles
./scripts/deploy-infrastructure.sh
```

### 3. Deploy Lambda Functions (2 minutes)

```bash
# Package and deploy both Lambda functions
./scripts/deploy-lambdas.sh
```

### 4. Deploy API Gateway (1 minute)

```bash
# Create webhook endpoint
./scripts/deploy-api-gateway.sh
```

**Copy the webhook URL from the output!**

## Test It (1 minute)

```bash
# Test the webhook
./scripts/test-webhook.sh https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod/webhook
```

Wait 10 minutes and check your Slack channel for the notification!

## Configure Your CRM

Point your CRM webhook to:
```
https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod/webhook
```

## Monitor

```bash
# Watch capture logs
aws logs tail /aws/lambda/crm-leads-capture --follow

# Watch refinement logs
aws logs tail /aws/lambda/crm-leads-refinement --follow

# Check S3 data
aws s3 ls s3://your-bucket/raw/ --recursive
aws s3 ls s3://your-bucket/refined/ --recursive
```

## What Happens?

1. **T+0s**: CRM sends webhook → Capture Lambda stores raw data in S3 and queues for processing
2. **T+600s** (10 min): SQS triggers Refinement Lambda → Data cleaned → Slack notification sent

## Troubleshooting

**Problem**: Deployment fails with "Access Denied"  
**Solution**: Check AWS credentials and IAM permissions

**Problem**: Slack notifications not working  
**Solution**: Verify `SLACK_WEBHOOK_URL` in `.env` is correct

**Problem**: Lambda timeouts  
**Solution**: Check CloudWatch Logs for specific errors

## Need Help?

- 📖 Read [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment guide
- 🏗️ Read [ARCHITECTURE.md](ARCHITECTURE.md) for system architecture
- 📚 Read [README.md](README.md) for complete documentation

## Cleanup

To remove all resources:
```bash
./scripts/teardown.sh
```

⚠️ **Warning**: This permanently deletes all data!

## Cost Estimate

For 10,000 leads/month: **~$0.12/month**

The serverless architecture means you only pay for what you use!

## Next Steps

- ✅ Set up CloudWatch alarms for errors
- ✅ Configure S3 lifecycle policies for data retention
- ✅ Add API authentication for production
- ✅ Set up monitoring dashboard
- ✅ Customize data cleaning logic for your needs

Happy automating! 🚀
