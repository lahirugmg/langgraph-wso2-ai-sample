# API Manager Integration Changes

This document describes the changes made to integrate the care-plan and evidence agents with an authenticated API Manager proxy instead of direct OpenAI API calls.

## Overview

Both agents (`care-plan-agent` and `evidence-agent`) have been updated to:
1. Use OAuth2 client credentials flow for authentication
2. Route all LLM requests through a configured API Manager endpoint
3. Cache access tokens to minimize authentication overhead

## Configuration

### Required Environment Variables

The following environment variables must be set (typically in a `.env` file):

```bash
# API Manager Base URL (your instance)
API_MANAGER_BASE_URL=https://eg-03e6b57c-d2ae-4de4-b142-e49de14cba1b-prod.e1-us-east-azure.bijiraapis.dev

# OAuth2 Client Credentials
API_MANAGER_CLIENT_ID=your_client_id_here
API_MANAGER_CLIENT_SECRET=your_client_secret_here

# Model to use (passed to the API)
OPENAI_MODEL=gpt-4o-mini
```

### Optional Configuration

```bash
# Override default token endpoint
API_MANAGER_TOKEN_ENDPOINT=https://your-api-manager/oauth2/token

# Override default chat completions endpoint
API_MANAGER_CHAT_ENDPOINT=https://your-api-manager/healthcare/openai-api/v1.0/chat/completions
```

If not specified, these will be derived from `API_MANAGER_BASE_URL`:
- Token endpoint: `${API_MANAGER_BASE_URL}/oauth2/token`
- Chat endpoint: `${API_MANAGER_BASE_URL}/healthcare/openai-api/v1.0/chat/completions`

## Changes Made

### 1. care-plan-agent/app.py

**Removed:**
- `OPENAI_API_KEY` environment variable
- `OPENAI_BASE_URL` environment variable
- Direct OpenAI API calls

**Added:**
- OAuth2 configuration variables
- `_get_access_token()` function for token management
- Token caching mechanism (60-second buffer before expiry)
- Updated `_call_llm()` to use API Manager endpoint with OAuth2

### 2. evidence-agent/evidence_agent.py

**Removed:**
- `OPENAI_API_KEY` environment variable
- `OPENAI_BASE_URL` environment variable
- Direct OpenAI API calls

**Added:**
- OAuth2 configuration variables
- `_get_access_token()` function for token management
- Token caching mechanism (60-second buffer before expiry)
- Updated `_call_llm()` to use API Manager endpoint with OAuth2

## Authentication Flow

1. **Token Request**: When an LLM call is needed, the agent first checks if a cached token exists and is still valid
2. **Client Credentials Grant**: If no valid token exists, it requests a new one using:
   ```
   POST ${API_MANAGER_TOKEN_ENDPOINT}
   Content-Type: application/x-www-form-urlencoded
   
   grant_type=client_credentials&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}
   ```
3. **Token Caching**: The access token and expiry time are cached to avoid unnecessary token requests
4. **API Call**: The cached token is used to authenticate LLM requests:
   ```
   POST ${API_MANAGER_CHAT_ENDPOINT}
   Authorization: Bearer {ACCESS_TOKEN}
   Content-Type: application/json
   
   {
     "model": "gpt-4o-mini",
     "messages": [...],
     "temperature": 0.1,
     "response_format": {"type": "json_object"}
   }
   ```

## Backward Compatibility

If API Manager credentials are not configured, the agents will:
- Log a message indicating the configuration is missing
- Skip LLM-based processing
- Fall back to heuristic/rule-based behavior (existing fallback logic)

This ensures the system remains functional even without API Manager integration.

## Testing

To test the integration:

1. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

2. Start the services:
   ```bash
   ./start_services.sh
   ```

3. Monitor logs for authentication messages:
   - "Requesting new access token from API Manager"
   - "Access token obtained successfully"
   - "Calling LLM model=... via API Manager"

4. Test the care-plan endpoint:
   ```bash
   curl -X POST http://localhost:8000/agents/care-plan/recommendation \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "dr_test",
       "patient_id": "12873",
       "question": "Test question"
     }'
   ```

## Security Considerations

- **Secrets Management**: Store `API_MANAGER_CLIENT_SECRET` securely (e.g., using secret management services)
- **Token Security**: Access tokens are cached in memory only and not persisted
- **HTTPS Required**: Always use HTTPS for API Manager endpoints in production
- **Token Expiry**: Tokens are refreshed automatically 60 seconds before expiry

## Troubleshooting

### "API Manager credentials not configured"
- Ensure all required environment variables are set
- Check that `.env` file is in the correct location and being loaded

### "Failed to obtain access token"
- Verify client ID and secret are correct
- Check token endpoint URL is accessible
- Review API Manager logs for authentication errors

### "LLM call failed"
- Check that chat endpoint URL is correct
- Verify the API Manager proxy is properly configured to forward to OpenAI
- Ensure the access token has appropriate scopes/permissions
