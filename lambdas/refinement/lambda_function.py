"""
Lambda function to refine and process CRM lead data.
This function is triggered by SQS after a 10-minute delay, retrieves the raw data from S3,
cleans and enriches it, stores the refined data, and sends a notification to Slack.
"""
import json
import boto3
import os
from datetime import datetime
import requests

s3_client = boto3.client('s3')

# Environment variables
S3_BUCKET = os.environ.get('S3_BUCKET')
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')


def lambda_handler(event, context):
    """
    Process leads from SQS queue after delay.
    
    Args:
        event: SQS event containing message(s)
        context: Lambda context object
        
    Returns:
        dict: Processing results
    """
    try:
        results = []
        
        # Process each SQS message
        for record in event['Records']:
            message = json.loads(record['body'])
            lead_id = message['lead_id']
            s3_key = message['s3_key']
            
            # Retrieve raw data from S3
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            raw_data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Clean and refine the lead data
            refined_data = refine_lead_data(raw_data)
            
            # Store refined data in S3
            refined_key = f"refined/{datetime.utcnow().strftime('%Y/%m/%d')}/{lead_id}.json"
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=refined_key,
                Body=json.dumps(refined_data, indent=2),
                ContentType='application/json'
            )
            
            # Send Slack notification
            send_slack_notification(refined_data)
            
            results.append({
                'lead_id': lead_id,
                'status': 'processed'
            })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {len(results)} lead(s)',
                'results': results
            })
        }
        
    except Exception as e:
        print(f"Error processing lead: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Error processing lead',
                'error': str(e)
            })
        }


def refine_lead_data(raw_data):
    """
    Clean and refine lead data.
    
    Args:
        raw_data: Raw lead data from S3
        
    Returns:
        dict: Refined lead data
    """
    # Extract raw payload
    raw_payload = raw_data.get('raw_data', {})
    
    # Clean and standardize data
    refined = {
        'lead_id': raw_data['lead_id'],
        'captured_at': raw_data['timestamp'],
        'processed_at': datetime.utcnow().isoformat(),
        'status': 'refined',
        'contact': {
            'name': clean_string(raw_payload.get('name', '')),
            'email': clean_email(raw_payload.get('email', '')),
            'phone': clean_phone(raw_payload.get('phone', '')),
            'company': clean_string(raw_payload.get('company', ''))
        },
        'lead_details': {
            'source': raw_payload.get('source', 'Unknown'),
            'campaign': raw_payload.get('campaign', ''),
            'lead_score': raw_payload.get('lead_score', 0),
            'owner': raw_payload.get('owner', 'Unassigned')
        },
        'metadata': {
            'original_data': raw_payload
        }
    }
    
    return refined


def clean_string(value):
    """Clean and trim string values."""
    if not value:
        return ''
    return str(value).strip()


def clean_email(email):
    """Clean and validate email."""
    if not email:
        return ''
    email = str(email).strip().lower()
    # Basic email validation
    if '@' in email and '.' in email.split('@')[1]:
        return email
    return ''


def clean_phone(phone):
    """Clean phone number."""
    if not phone:
        return ''
    # Remove common non-numeric characters
    cleaned = ''.join(c for c in str(phone) if c.isdigit() or c in ['+', '-', '(', ')', ' '])
    return cleaned.strip()


def send_slack_notification(lead_data):
    """
    Send notification to Slack about new lead.
    
    Args:
        lead_data: Refined lead data
    """
    if not SLACK_WEBHOOK_URL:
        print("Slack webhook URL not configured, skipping notification")
        return
    
    contact = lead_data.get('contact', {})
    details = lead_data.get('lead_details', {})
    
    # Format Slack message
    message = {
        'text': '🎯 New Lead Alert',
        'blocks': [
            {
                'type': 'header',
                'text': {
                    'type': 'plain_text',
                    'text': '🎯 New Lead Captured'
                }
            },
            {
                'type': 'section',
                'fields': [
                    {
                        'type': 'mrkdwn',
                        'text': f"*Name:*\n{contact.get('name', 'N/A')}"
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f"*Company:*\n{contact.get('company', 'N/A')}"
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f"*Email:*\n{contact.get('email', 'N/A')}"
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f"*Phone:*\n{contact.get('phone', 'N/A')}"
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f"*Source:*\n{details.get('source', 'N/A')}"
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f"*Owner:*\n{details.get('owner', 'Unassigned')}"
                    }
                ]
            },
            {
                'type': 'context',
                'elements': [
                    {
                        'type': 'mrkdwn',
                        'text': f"Lead ID: {lead_data['lead_id']} | Processed: {lead_data['processed_at']}"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=message,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        response.raise_for_status()
        print(f"Slack notification sent successfully for lead {lead_data['lead_id']}")
    except Exception as e:
        print(f"Error sending Slack notification: {str(e)}")
