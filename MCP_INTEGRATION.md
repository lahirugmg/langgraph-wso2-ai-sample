# MCP Integration Guide

## Overview

The Care Plan Agent and Evidence Agent have been updated to consume backend services through the **Model Context Protocol (MCP)** instead of direct REST API calls. This provides a standardized, secure way to access healthcare data through authenticated gateways.

## Architecture

```
┌─────────────────────┐
│  Care Plan Agent    │
│  (Port 8000)        │
└──────────┬──────────┘
           │
           │ MCP Tools
           │
           ├──────────────────────────┐
           │                          │
           ▼                          ▼
    ┌────────────┐            ┌─────────────────┐
    │ EHR MCP    │            │ Evidence Agent  │
    │ Server     │            │ (Port 8003)     │
    └────────────┘            └────────┬────────┘
                                       │
                                       │ MCP Tools
                                       │
                                       ▼
                              ┌──────────────────┐
                              │ Trial Registry   │
                              │ MCP Server       │
                              └──────────────────┘
```

## MCP Server Configuration

### Environment Variables

Both agents require the following environment variables in their `.env` files:

```bash
# MCP Gateway OAuth2 Configuration
MCP_GATEWAY_TOKEN_ENDPOINT=https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.choreosts.dev/oauth2/token
MCP_GATEWAY_CLIENT_ID="lq3DxzFSYTDTighlOvLkKrPc7VpG"
MCP_GATEWAY_CLIENT_SECRET="cm4lMNG7teYcZPVlS8PWE2GmpwL0"

# MCP Server URLs
EHR_MCP_URL=https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.bijiraapis.dev/clinicagent/ehr-mcp/v1.0/mcp
TRIAL_REGISTRY_MCP_URL=https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.bijiraapis.dev/clinicagent/trial-registry-mcp/v1.0/mcp
```

### MCP Server Details

#### 1. EHR MCP Server

**URL:** `https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.bijiraapis.dev/clinicagent/ehr-mcp/v1.0/mcp`

**Available Tools:**
- `getPatientsIdSummary` - Get patient summary by ID
  - Parameters: `{"id": "patient_id"}`
  - Returns: Patient demographics, problems, medications, labs

- `getPatientsIdLabs` - Get patient lab results
  - Parameters: `{"id": "patient_id"}`
  - Returns: Laboratory test results

- `postOrdersMedication` - Create medication orders
  - Parameters: Medication order details
  - Returns: Order confirmation

#### 2. Trial Registry MCP Server

**URL:** `https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.bijiraapis.dev/clinicagent/trial-registry-mcp/v1.0/mcp`

**Available Tools:**
- `getTrials` - Get all clinical trials
  - Parameters: `{}`
  - Returns: List of clinical trials with eligibility criteria

## Implementation Details

### Care Plan Agent Changes

The Care Plan Agent (`care-plan-agent/app.py`) has been updated with:

1. **MCP Client Functions**:
   - `_get_mcp_access_token()` - OAuth2 authentication for MCP gateway
   - `_call_mcp_tool()` - Generic MCP tool caller

2. **Updated `fetch_patient_summary()` Function**:
   ```python
   # First tries EHR MCP server
   if EHR_MCP_URL:
       mcp_result = _call_mcp_tool(EHR_MCP_URL, "getPatientsIdSummary", {"id": patient_id})
       # Extract and parse response
   
   # Falls back to direct REST API if MCP fails
   if not summary:
       response = requests.get(f"{EHR_SERVICE_URL}/patients/{patient_id}/summary")
   ```

3. **Graceful Fallback**: If MCP calls fail, the agent automatically falls back to direct REST API calls

### Evidence Agent Changes

The Evidence Agent (`evidence-agent/evidence_agent.py`) has been updated with:

1. **MCP Client Functions**:
   - `_get_mcp_access_token()` - OAuth2 authentication for MCP gateway
   - `_call_mcp_tool()` - Generic MCP tool caller

2. **Updated `fetch_trials()` Function**:
   ```python
   # First tries Trial Registry MCP server
   if TRIAL_REGISTRY_MCP_URL:
       mcp_result = _call_mcp_tool(TRIAL_REGISTRY_MCP_URL, "getTrials", {})
       # Extract and parse response
   
   # Falls back to direct REST API if MCP fails
   if not trials:
       response = requests.get(f"{TRIAL_REGISTRY_URL}/trials")
   ```

3. **Graceful Fallback**: If MCP calls fail, the agent falls back to direct REST API calls

## OAuth2 Authentication Flow

```
1. Agent needs to call MCP tool
2. Check if access token is cached and valid
3. If not, request new token:
   POST https://.../oauth2/token
   Body: {
     "grant_type": "client_credentials",
     "client_id": "...",
     "client_secret": "..."
   }
4. Cache token with expiry time
5. Use Bearer token for MCP tool calls
```

## MCP Protocol

### Request Format

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "getPatientsIdSummary",
    "arguments": {
      "id": "12873"
    }
  }
}
```

### Response Format

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"patient_id\": \"12873\", ...}"
      }
    ],
    "isError": false
  }
}
```

### Error Response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Internal server error"
  }
}
```

## Testing

### Quick Test

```bash
# Test Evidence Agent with MCP
curl -X POST "http://localhost:8003/agents/evidence/search" \
  -H "Content-Type: application/json" \
  -d '{
    "age": 68,
    "diagnosis": "Type 2 diabetes mellitus with chronic kidney disease",
    "egfr": 45.2,
    "comorbidities": ["hypertension"],
    "geo": {"lat": 35.15, "lon": -90.05, "radius_km": 30}
  }'

# Test Care Plan Agent with MCP
curl -X POST "http://localhost:8000/care-plan" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "patient_id": "12873",
    "question": "What treatment is recommended?"
  }'
```

### Comprehensive Test Suite

```bash
python3 test_mcp_integration.py
```

This will test:
1. Evidence Agent with MCP Trial Registry
2. Care Plan Agent with MCP EHR and Evidence Agent

## Logging

Both agents provide detailed logging for MCP operations:

```
2025-10-08 12:00:00 [INFO] care-plan-agent: Requesting new MCP access token
2025-10-08 12:00:00 [INFO] care-plan-agent: ✓ MCP access token obtained successfully
2025-10-08 12:00:01 [INFO] care-plan-agent: Using EHR MCP server: https://...
2025-10-08 12:00:01 [INFO] care-plan-agent: Calling MCP tool 'getPatientsIdSummary'
2025-10-08 12:00:02 [INFO] care-plan-agent: ✓ MCP tool 'getPatientsIdSummary' executed successfully
2025-10-08 12:00:02 [INFO] care-plan-agent: ✓ EHR summary received via MCP
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check MCP_GATEWAY_CLIENT_ID and MCP_GATEWAY_CLIENT_SECRET
   - Verify token endpoint URL
   - Ensure credentials are not wrapped in extra quotes

2. **Internal Server Error (-32603)**
   - Check MCP server is running
   - Verify tool name and parameter format
   - Check MCP server logs for backend issues

3. **Timeout Errors**
   - Increase timeout values in requests
   - Check network connectivity to MCP servers

4. **Fallback to Direct Service**
   - This is normal if MCP servers are unavailable
   - Check logs for specific MCP error messages

### Debug Mode

Enable detailed logging:

```python
logger.setLevel(logging.DEBUG)
```

## Benefits of MCP Integration

1. **Standardized Protocol**: Consistent interface across all healthcare services
2. **Security**: OAuth2-based authentication through API gateway
3. **Flexibility**: Easy to add new MCP tools without changing agent code
4. **Reliability**: Graceful fallback to direct APIs if MCP unavailable
5. **Observability**: Centralized logging and monitoring through gateway

## Migration Notes

### Old Way (Direct REST)
```python
response = requests.get(f"{EHR_SERVICE_URL}/patients/{patient_id}/summary")
summary = response.json()
```

### New Way (MCP Protocol)
```python
mcp_result = _call_mcp_tool(EHR_MCP_URL, "getPatientsIdSummary", {"id": patient_id})
content = mcp_result.get("content", [])[0].get("text", "")
summary = json.loads(content)
```

## Future Enhancements

- [ ] Add support for more MCP tools (medications, allergies, etc.)
- [ ] Implement MCP tool discovery (list available tools dynamically)
- [ ] Add caching layer for frequently accessed MCP data
- [ ] Implement circuit breaker pattern for MCP failures
- [ ] Add metrics and monitoring for MCP call performance

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [OAuth2 Client Credentials Flow](https://oauth.net/2/grant-types/client-credentials/)
- [WSO2 API Manager Documentation](https://apim.docs.wso2.com)
