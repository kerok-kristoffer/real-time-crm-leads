"""
Lambda function to capture CRM webhook data.
This function receives webhook POST requests from the CRM, stores raw data in S3,
and sends a message to SQS for delayed processing.
"""
import json
import boto3
import os
from datetime import datetime
import uuid

s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')

# Environment variables
S3_BUCKET = os.environ.get('S3_BUCKET')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')


def lambda_handler(event, context):
    """
    Handle incoming webhook from CRM.
    
    Args:
        event: API Gateway event containing the webhook payload
        context: Lambda context object
        
    Returns:
        dict: API Gateway response
    """
    try:
        # Parse the webhook payload
        if 'body' in event:
            if isinstance(event['body'], str):
                payload = json.loads(event['body'])
            else:
                payload = event['body']
        else:
            payload = event
        
        # Generate unique ID for this lead
        lead_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Add metadata to the payload
        lead_data = {
            'lead_id': lead_id,
            'timestamp': timestamp,
            'raw_data': payload,
            'status': 'captured'
        }
        
        # Store raw data in S3
        s3_key = f"raw/{datetime.utcnow().strftime('%Y/%m/%d')}/{lead_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(lead_data, indent=2),
            ContentType='application/json'
        )
        
        # Send message to SQS with 10-minute delay
        sqs_message = {
            'lead_id': lead_id,
            's3_key': s3_key,
            'timestamp': timestamp
        }
        
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(sqs_message),
            DelaySeconds=600  # 10 minutes delay
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': 'Lead captured successfully',
                'lead_id': lead_id
            })
        }
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': 'Error capturing lead',
                'error': str(e)
            })
        }
