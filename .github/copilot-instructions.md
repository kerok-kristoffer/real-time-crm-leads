# GitHub Copilot Instructions

## Project Overview

This is a real-time CRM leads management system that automates lead capture and assignment. The system:
- Captures newly created leads via CRM webhooks
- Implements a buffer period (e.g., 10 minutes) to allow for CRM updates
- Assigns leads to the correct owner based on CRM-updated information
- Notifies sales teams in real-time via Slack or email with enriched lead data

## Technology Stack

- **Language**: Python
- **Architecture**: Event-driven webhook-based system
- **Integrations**: CRM webhooks, Slack, Email notifications

## Coding Guidelines

### Python Style
- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and single-purpose

### Error Handling
- Implement proper error handling for webhook failures
- Log errors appropriately for debugging
- Ensure graceful degradation when external services are unavailable

### Testing
- Write unit tests for business logic
- Test webhook endpoints thoroughly
- Mock external API calls in tests

### Dependencies
- Use virtual environments for dependency isolation
- Keep dependencies minimal and well-documented
- Pin dependency versions for reproducibility

## Architecture Considerations

### Webhook Handling
- Validate webhook signatures for security
- Handle idempotent requests (duplicate webhooks)
- Implement retry logic for failed operations

### Lead Assignment
- Ensure thread-safe operations for concurrent requests
- Implement proper queueing for the buffer period
- Handle edge cases (missing data, invalid leads, etc.)

### Notifications
- Batch notifications when appropriate
- Include relevant lead data in notifications
- Handle notification failures gracefully

## Security

- Never commit API keys, tokens, or credentials
- Use environment variables for configuration
- Validate and sanitize all webhook input
- Implement rate limiting for webhook endpoints

## Performance

- Optimize database queries
- Use async operations where appropriate
- Monitor and log processing times
- Implement caching for frequently accessed data
