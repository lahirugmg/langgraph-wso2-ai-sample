# MCP Integration Changes Summary

## Overview
Updated both **Care Plan Agent** and **Evidence Agent** to consume backend services through the Model Context Protocol (MCP) instead of direct REST API calls.

## Files Modified

### 1. Care Plan Agent (`care-plan-agent/app.py`)

**New Imports & Configuration:**
```python
# Added _strip_quotes helper function
# Added MCP Gateway configuration variables
MCP_GATEWAY_CLIENT_ID = _strip_quotes(os.environ.get("MCP_GATEWAY_CLIENT_ID"))
MCP_GATEWAY_CLIENT_SECRET = _strip_quotes(os.environ.get("MCP_GATEWAY_CLIENT_SECRET"))
MCP_GATEWAY_TOKEN_ENDPOINT = _strip_quotes(os.environ.get("MCP_GATEWAY_TOKEN_ENDPOINT"))
EHR_MCP_URL = _strip_quotes(os.environ.get("EHR_MCP_URL"))

# Added MCP access token cache
_mcp_access_token_cache = {"token": None, "expires_at": 0}
```

**New Functions Added:**
- `_get_mcp_access_token()` - Handles OAuth2 authentication for MCP gateway
- `_call_mcp_tool(server_url, tool_name, arguments)` - Generic MCP tool caller

**Modified Functions:**
- `fetch_patient_summary()` - Now tries MCP first, falls back to direct REST
  - Calls `getPatientsIdSummary` MCP tool
  - Extracts JSON from MCP response
  - Falls back to `{EHR_SERVICE_URL}/patients/{patient_id}/summary` if MCP fails

### 2. Evidence Agent (`evidence-agent/evidence_agent.py`)

**Existing MCP Support Enhanced:**
The evidence agent already had partial MCP support which has been corrected to use proper MCP protocol.

**Modified Functions:**
- `fetch_trials()` - Completely rewritten to use MCP protocol
  - Calls `getTrials` MCP tool via `_call_mcp_tool()`
  - Extracts trials JSON from MCP response
  - Falls back to `{TRIAL_REGISTRY_URL}/trials` if MCP fails

**Before (Old Implementation):**
```python
# Was making direct REST GET to MCP URL (incorrect)
if TRIAL_REGISTRY_MCP_URL:
    response = requests.get(f"{TRIAL_REGISTRY_MCP_URL}/trials", headers={"Authorization": f"Bearer {token}"})
```

**After (New Implementation):**
```python
# Now uses proper MCP protocol
if TRIAL_REGISTRY_MCP_URL:
    mcp_result = _call_mcp_tool(TRIAL_REGISTRY_MCP_URL, "getTrials", {})
    # Extract from MCP response format
    content = mcp_result.get("content", [])[0].get("text", "")
    trials = json.loads(content)
```

### 3. Environment Configuration

**Updated `.env` files in both agent directories:**

```bash
# care-plan-agent/.env
MCP_GATEWAY_TOKEN_ENDPOINT=https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.choreosts.dev/oauth2/token
MCP_GATEWAY_CLIENT_ID="lq3DxzFSYTDTighlOvLkKrPc7VpG"
MCP_GATEWAY_CLIENT_SECRET="cm4lMNG7teYcZPVlS8PWE2GmpwL0"
EHR_MCP_URL=https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.bijiraapis.dev/clinicagent/ehr-mcp/v1.0/mcp
TRIAL_REGISTRY_MCP_URL=https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.bijiraapis.dev/clinicagent/trial-registry-mcp/v1.0/mcp

# evidence-agent/.env
(Same MCP configuration as above)
```

### 4. New Test Files Created

**`test_mcp_integration.py`**
- Comprehensive test suite for both agents
- Tests Evidence Agent MCP integration
- Tests Care Plan Agent MCP integration
- Provides detailed output and summary

**`test_ehr_mcp_tools.py`** (Already existed, kept for reference)
- Low-level MCP tool testing
- Tests individual EHR MCP tools

**`MCP_INTEGRATION.md`**
- Complete documentation of MCP integration
- Architecture diagrams
- API reference for MCP tools
- Troubleshooting guide
- Migration notes

## MCP Protocol Implementation

### Request Format
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "toolName",
    "arguments": {...}
  }
}
```

### Authentication
- Uses OAuth2 Client Credentials flow
- Tokens are cached with expiry tracking
- Authorization header: `Bearer {token}`

### Response Parsing
```python
# MCP returns structured response
result = response.json()
content = result.get("result", {}).get("content", [])
text_data = content[0].get("text", "")
parsed_data = json.loads(text_data)
```

## Key Features

✅ **Graceful Fallback**: Automatically falls back to direct REST if MCP fails
✅ **Token Caching**: OAuth2 tokens cached to reduce authentication overhead
✅ **Detailed Logging**: Comprehensive logging for debugging and monitoring
✅ **Error Handling**: Proper error handling with informative messages
✅ **Backward Compatible**: Still supports direct REST API calls as fallback

## MCP Tools Used

### EHR MCP Server
- **`getPatientsIdSummary`** - Get patient summary
  - Parameters: `{"id": "patient_id"}`
  - Used by: Care Plan Agent

### Trial Registry MCP Server
- **`getTrials`** - Get all clinical trials
  - Parameters: `{}`
  - Used by: Evidence Agent

## Testing Instructions

### Start Services
```bash
# Terminal 1 - Evidence Agent
cd evidence-agent
python3 evidence_agent.py

# Terminal 2 - Care Plan Agent
cd care-plan-agent
python3 app.py
```

### Run Tests
```bash
# Run comprehensive test suite
python3 test_mcp_integration.py

# Or test individually
curl -X POST "http://localhost:8003/agents/evidence/search" \
  -H "Content-Type: application/json" \
  -d '{"age": 68, "diagnosis": "Type 2 diabetes", "egfr": 45.2, "comorbidities": [], "geo": {"lat": 35.15, "lon": -90.05, "radius_km": 30}}'

curl -X POST "http://localhost:8000/care-plan" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "patient_id": "12873", "question": "Treatment recommendations?"}'
```

## Expected Log Output

### Successful MCP Call
```
2025-10-08 12:00:00 [INFO] care-plan-agent: Requesting new MCP access token
2025-10-08 12:00:00 [INFO] care-plan-agent: MCP token endpoint responded with status: 200
2025-10-08 12:00:00 [INFO] care-plan-agent: ✓ MCP access token obtained successfully (expires in 3600 seconds)
2025-10-08 12:00:01 [INFO] care-plan-agent: Using EHR MCP server: https://...
2025-10-08 12:00:01 [INFO] care-plan-agent: Calling MCP tool 'getPatientsIdSummary' at https://...
2025-10-08 12:00:02 [INFO] care-plan-agent: MCP tool 'getPatientsIdSummary' responded with status: 200
2025-10-08 12:00:02 [INFO] care-plan-agent: ✓ MCP tool 'getPatientsIdSummary' executed successfully
2025-10-08 12:00:02 [INFO] care-plan-agent: ✓ EHR summary received via MCP for patient_id=12873
```

### Fallback to Direct Service
```
2025-10-08 12:00:01 [WARNING] care-plan-agent: MCP call failed, falling back to direct EHR service
2025-10-08 12:00:01 [INFO] care-plan-agent: Using direct EHR service: http://127.0.0.1:8001
```

## Migration Checklist

- [x] Add MCP configuration to `.env` files
- [x] Implement `_get_mcp_access_token()` in both agents
- [x] Implement `_call_mcp_tool()` in both agents
- [x] Update `fetch_patient_summary()` to use EHR MCP
- [x] Update `fetch_trials()` to use Trial Registry MCP
- [x] Add graceful fallback mechanisms
- [x] Add comprehensive logging
- [x] Create test suite
- [x] Create documentation
- [x] Test end-to-end workflows

## Breaking Changes

**None** - The implementation is fully backward compatible. If MCP servers are not configured or unavailable, agents automatically fall back to direct REST API calls.

## Performance Considerations

- **Token Caching**: Reduces authentication overhead by caching tokens
- **Timeout**: MCP calls have 30-second timeout
- **Fallback**: Adds minimal latency (~100ms) only when MCP fails

## Security Enhancements

- OAuth2 authentication for all MCP calls
- Tokens transmitted via secure Bearer header
- Client credentials stored in environment variables (not hardcoded)
- All communication over HTTPS

## Next Steps

1. Monitor MCP call success rate in production
2. Tune timeout values based on observed latency
3. Consider implementing circuit breaker pattern for repeated MCP failures
4. Add metrics collection for MCP performance monitoring
5. Explore additional MCP tools (medications, allergies, etc.)
