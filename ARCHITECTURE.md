# System Architecture

## Overview

This document describes the technical architecture of the Real-Time CRM Leads Automation system.

## High-Level Architecture

```
┌─────────────┐
│     CRM     │
│   System    │
└──────┬──────┘
       │ HTTP POST (Webhook)
       │
       ▼
┌─────────────────────────────────────────────────────┐
│                   AWS Cloud                          │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │          API Gateway (REST API)            │    │
│  │     POST /webhook endpoint                 │    │
│  └────────────────┬───────────────────────────┘    │
│                   │                                  │
│                   ▼                                  │
│  ┌─────────────────────────────────────┐           │
│  │   Capture Lambda Function           │           │
│  │   - Parse webhook payload           │           │
│  │   - Generate unique lead ID         │           │
│  │   - Store raw data in S3            │           │
│  │   - Send message to SQS             │           │
│  └─────┬───────────────────────┬───────┘           │
│        │                       │                    │
│        ▼                       ▼                    │
│  ┌──────────┐          ┌─────────────┐             │
│  │ S3 Bucket│          │  SQS Queue  │             │
│  │  /raw/   │          │ (10 min     │             │
│  │          │          │  delay)     │             │
│  └──────────┘          └──────┬──────┘             │
│                               │                     │
│                               ▼                     │
│  ┌─────────────────────────────────────┐           │
│  │   Refinement Lambda Function        │           │
│  │   - Retrieve raw data from S3       │           │
│  │   - Clean and validate data         │           │
│  │   - Enrich lead information         │           │
│  │   - Store refined data in S3        │           │
│  │   - Send Slack notification         │           │
│  └─────┬───────────────────────┬───────┘           │
│        │                       │                    │
│        ▼                       ▼                    │
│  ┌──────────┐          ┌─────────────┐             │
│  │ S3 Bucket│          │   Slack     │             │
│  │/refined/ │          │   Webhook   │             │
│  └──────────┘          └─────────────┘             │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Component Details

### 1. API Gateway

**Purpose**: HTTP endpoint for receiving CRM webhooks

**Configuration**:
- Type: REST API
- Method: POST
- Resource: `/webhook`
- Authorization: None (consider adding API key for production)
- Integration: AWS_PROXY to Capture Lambda

**Request Flow**:
1. Receives POST request from CRM
2. Validates request format
3. Invokes Capture Lambda synchronously
4. Returns response to CRM

**Response Format**:
```json
{
  "statusCode": 200,
  "body": {
    "message": "Lead captured successfully",
    "lead_id": "uuid"
  }
}
```

### 2. Capture Lambda Function

**Purpose**: Initial webhook processing and data capture

**Runtime**: Python 3.11  
**Memory**: 256 MB  
**Timeout**: 30 seconds

**Environment Variables**:
- `S3_BUCKET`: Target S3 bucket name
- `SQS_QUEUE_URL`: SQS queue URL for delayed processing

**Execution Flow**:
1. Parse incoming webhook payload
2. Generate UUID for lead tracking
3. Add metadata (timestamp, status)
4. Store raw data to S3 at `raw/YYYY/MM/DD/{lead_id}.json`
5. Send message to SQS with 600-second delay
6. Return success response

**Error Handling**:
- Catches all exceptions
- Logs errors to CloudWatch
- Returns 500 status with error details

**IAM Permissions Required**:
- `s3:PutObject` on target bucket
- `sqs:SendMessage` on target queue
- CloudWatch Logs write permissions

### 3. SQS Queue

**Purpose**: Decouple capture from refinement with configurable delay

**Configuration**:
- Delay: 0 seconds (delay applied per-message)
- Message Retention: 14 days
- Visibility Timeout: 300 seconds (5 minutes)

**Message Format**:
```json
{
  "lead_id": "uuid",
  "s3_key": "raw/YYYY/MM/DD/uuid.json",
  "timestamp": "ISO-8601 timestamp"
}
```

**Why SQS?**:
- Automatic retry on failure
- Dead-letter queue support (recommended for production)
- Scalable message processing
- Built-in monitoring via CloudWatch

**Delay Mechanism**:
The 10-minute delay is implemented using the `DelaySeconds` parameter in the `SendMessage` API call, allowing per-message delays up to 15 minutes.

### 4. Refinement Lambda Function

**Purpose**: Data cleaning, enrichment, and notification

**Runtime**: Python 3.11  
**Memory**: 512 MB  
**Timeout**: 60 seconds

**Environment Variables**:
- `S3_BUCKET`: Target S3 bucket name
- `SLACK_WEBHOOK_URL`: Slack incoming webhook URL

**Execution Flow**:
1. Triggered by SQS event (batch of up to 10 messages)
2. For each message:
   - Retrieve raw data from S3
   - Clean and validate fields:
     - Trim whitespace
     - Normalize email (lowercase)
     - Clean phone numbers
     - Validate data format
   - Enrich with metadata
   - Store refined data to S3 at `refined/YYYY/MM/DD/{lead_id}.json`
   - Send formatted notification to Slack
3. Return batch processing results

**Data Transformations**:
- String fields: trimmed, normalized
- Email: lowercased, basic validation
- Phone: formatted, cleaned of special characters
- Enrichment: add processing timestamp, status

**Error Handling**:
- Per-message error handling
- Continues processing batch even if one fails
- Logs all errors to CloudWatch
- Failed messages return to SQS for retry

**IAM Permissions Required**:
- `s3:GetObject` and `s3:PutObject` on target bucket
- `sqs:ReceiveMessage` and `sqs:DeleteMessage` on queue
- CloudWatch Logs write permissions

### 5. S3 Bucket

**Purpose**: Persistent storage for lead data

**Structure**:
```
s3://bucket-name/
├── raw/
│   └── YYYY/
│       └── MM/
│           └── DD/
│               ├── {lead-id-1}.json
│               ├── {lead-id-2}.json
│               └── ...
└── refined/
    └── YYYY/
        └── MM/
            └── DD/
                ├── {lead-id-1}.json
                ├── {lead-id-2}.json
                └── ...
```

**Configuration**:
- Versioning: Enabled
- Encryption: Recommended (not configured by default)
- Lifecycle: Not configured (consider adding)

**Data Format** (Raw):
```json
{
  "lead_id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z",
  "raw_data": {
    "name": "John Doe",
    "email": "john@example.com",
    ...
  },
  "status": "captured"
}
```

**Data Format** (Refined):
```json
{
  "lead_id": "uuid",
  "captured_at": "2024-01-15T10:30:00Z",
  "processed_at": "2024-01-15T10:40:00Z",
  "status": "refined",
  "contact": {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1-555-0123",
    "company": "Example Inc"
  },
  "lead_details": {
    "source": "Website Form",
    "campaign": "Q4 2024",
    "lead_score": 85,
    "owner": "sales@example.com"
  },
  "metadata": {
    "original_data": { ... }
  }
}
```

### 6. Slack Integration

**Purpose**: Real-time notification to sales team

**Integration Type**: Incoming Webhook

**Message Format**:
- Rich Block Kit formatting
- Header with emoji indicator
- Structured fields (name, company, email, etc.)
- Footer with lead ID and timestamp

**Example Notification**:
```
🎯 New Lead Captured

Name: John Doe          Company: Example Inc
Email: john@example.com Phone: +1-555-0123
Source: Website Form    Owner: sales@example.com

Lead ID: abc123... | Processed: 2024-01-15T10:40:00Z
```

**Error Handling**:
- Logs errors but doesn't fail Lambda execution
- Allows system to continue even if Slack is down
- 10-second timeout on HTTP request

## Data Flow Timing

| Event | Time | Description |
|-------|------|-------------|
| Webhook received | T+0s | CRM sends lead to API Gateway |
| Data captured | T+1s | Raw data stored in S3, message sent to SQS |
| Waiting period | T+1s to T+600s | Message sits in SQS queue |
| Processing starts | T+600s | SQS triggers Refinement Lambda |
| Refinement complete | T+602s | Cleaned data stored, Slack sent |
| **Total time** | **~10 minutes** | From capture to notification |

## Security Architecture

### IAM Roles and Policies

**Lambda Execution Role**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::bucket-name/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage"
      ],
      "Resource": "arn:aws:sqs:region:account:queue-name"
    }
  ]
}
```

### Network Security

- All components within AWS VPC (optional, not configured by default)
- HTTPS encryption for all API Gateway traffic
- IAM-based service-to-service authentication
- No public internet access required for Lambda functions

### Data Security

- Secrets stored as environment variables (consider Secrets Manager for production)
- `.env` file excluded from version control
- S3 versioning enables data recovery
- CloudWatch logs retain for audit trail

## Scalability

### Current Limits

| Component | Limit | Notes |
|-----------|-------|-------|
| API Gateway | 10,000 RPS | Default regional limit |
| Lambda (Capture) | 1,000 concurrent | Account limit |
| Lambda (Refinement) | 1,000 concurrent | Account limit |
| SQS | Unlimited | Practically unlimited throughput |
| S3 | Unlimited | Unlimited storage and requests |

### Scaling Considerations

**Low Volume** (< 100 leads/day):
- Default configuration sufficient
- Cost: ~$1-5/month

**Medium Volume** (100-10,000 leads/day):
- Consider reserved concurrency for Lambdas
- Monitor SQS queue depth
- Cost: ~$5-50/month

**High Volume** (> 10,000 leads/day):
- Enable Lambda auto-scaling
- Use SQS FIFO if ordering matters
- Consider DynamoDB for faster querying
- Cost: ~$50-500/month

### Performance Optimization

1. **Reduce Lambda cold starts**: Use provisioned concurrency
2. **Batch SQS processing**: Already configured (up to 10 messages)
3. **Optimize S3 access**: Use S3 Transfer Acceleration for large files
4. **Parallel processing**: Multiple refinement Lambda instances run in parallel

## Monitoring and Observability

### CloudWatch Metrics

**API Gateway**:
- Count (requests)
- 4XXError, 5XXError
- Latency (average, p95, p99)

**Lambda Functions**:
- Invocations
- Errors
- Duration
- Throttles
- Concurrent Executions

**SQS Queue**:
- ApproximateNumberOfMessages
- ApproximateAgeOfOldestMessage
- NumberOfMessagesSent
- NumberOfMessagesDeleted

**S3 Bucket**:
- BucketSizeBytes
- NumberOfObjects

### Logging Strategy

All components log to CloudWatch Logs:
- `/aws/lambda/crm-leads-capture`
- `/aws/lambda/crm-leads-refinement`
- `/aws/apigateway/crm-webhook-api`

**Log Retention**: 7 days (default, consider extending)

### Alerting Recommendations

1. **High Error Rate**: Lambda errors > 5% over 5 minutes
2. **Queue Backup**: SQS messages > 1000
3. **Processing Delay**: Oldest message age > 15 minutes
4. **Lambda Throttling**: Any throttle events
5. **API Gateway 5XX**: Any 5XX errors

## Disaster Recovery

### Backup Strategy

- **S3 Data**: Versioning enabled, cross-region replication optional
- **Code**: Stored in Git repository
- **Configuration**: Documented in `.env` file

### Recovery Procedures

1. **Lambda Function Failure**: Automatic retries by SQS (3 times by default)
2. **S3 Bucket Loss**: Restore from versioning or cross-region replica
3. **Complete Region Failure**: Redeploy in different region using scripts

### RTO/RPO

- **Recovery Time Objective (RTO)**: ~15 minutes
- **Recovery Point Objective (RPO)**: ~0 (no data loss with S3 versioning)

## Cost Optimization

### Monthly Cost Breakdown (10,000 leads/month)

| Service | Usage | Cost |
|---------|-------|------|
| API Gateway | 10,000 requests | $0.04 |
| Lambda (Capture) | 10,000 * 1s | $0.02 |
| Lambda (Refinement) | 10,000 * 2s | $0.04 |
| SQS | 10,000 messages | $0.00 (free tier) |
| S3 | ~50 MB storage | $0.01 |
| Data Transfer | Minimal | $0.01 |
| **Total** | | **~$0.12/month** |

### Cost Reduction Tips

1. Adjust Lambda memory to minimum required
2. Use S3 lifecycle policies to archive old data
3. Optimize Lambda execution time
4. Use S3 Intelligent-Tiering for storage

## Future Enhancements

### Potential Improvements

1. **Dead Letter Queue**: Handle permanently failed messages
2. **DynamoDB Integration**: Fast querying of lead data
3. **Email Notifications**: Alternative to Slack
4. **API Authentication**: API keys or OAuth
5. **Lead Deduplication**: Check for duplicate leads
6. **CRM Sync-back**: Update CRM with enriched data
7. **Analytics Dashboard**: Real-time metrics and insights
8. **A/B Testing**: Different refinement strategies
9. **Machine Learning**: Lead scoring and assignment automation

### Migration Paths

**To Serverless Framework**:
- Convert to `serverless.yml` configuration
- Unified deployment process

**To CDK/CloudFormation**:
- Infrastructure as Code
- Version-controlled infrastructure
- Automated stack updates

**To Step Functions**:
- Complex workflows
- Visual workflow monitoring
- More sophisticated error handling
