#!/usr/bin/env python3
"""
Enhanced MCP Test Script - Testing specific EHR tools with correct parameters
"""

import json
import logging
import requests
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_ehr_tools():
    """Test specific EHR MCP tools with correct parameters."""
    
    server_url = "https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.bijiraapis.dev/clinicagent/ehr-mcp/v1.0/mcp"
    auth_token = "eyJ4NXQjUzI1NiI6ImVmalpEVEE4ZXFUbTMwYUE4LW1wNTFya2x1NnlhcW52UzZWZW92U3hRVHMiLCJraWQiOiI4OTBkZGZhNS00YTQwLTQ1OTQtYTFjMy04YWRlOGQwM2IzMWEjNmQwODNhZmYtMWMyYy00ODJiLWJlZGEtYzkyNjQzNjcyMjkwIiwiYWxnIjoiUlMyNTYifQ.eyJzdWIiOiJscTNEeHpGU1lURFRpZ2hsT3ZMa0tyUGM3VnBHIiwiYXVkIjoibHEzRHh6RlNZVERUaWdobE92TGtLclBjN1ZwRyIsImF1dCI6IkFQUExJQ0FUSU9OIiwibmJmIjoxNzU5OTQwOTg3LCJhenAiOiJscTNEeHpGU1lURFRpZ2hsT3ZMa0tyUGM3VnBHIiwib3JnYW5pemF0aW9uIjp7InV1aWQiOiI4OTBkZGZhNS00YTQwLTQ1OTQtYTFjMy04YWRlOGQwM2IzMWEifSwic2NvcGUiOiIiLCJpc3MiOiJodHRwczovLzg5MGRkZmE1LTRhNDAtNDU5NC1hMWMzLThhZGU4ZDAzYjMxYS1wcm9kLmUxLXVzLWVhc3QtYXp1cmUuY2hvcmVvc3RzLmRldi9vYXV0aDIvdG9rZW4iLCJleHAiOjE3NjA5NDA5NDcsImlhdCI6MTc1OTk0MDk4NywianRpIjoiNjdiOTEwMzEtYzc5YS00NGUyLWFjYjEtNmY4MWI1OWFkNGQ2In0.PeY8m4YAkWXy38ErhZ71LWFZNjJUjabSK1AwGTvPVvCSwofaGc1aa2s1QreqOnW07IhzKBGWropEveBV9X8Q8sc15bBCM8Jyd2pX3KhjQ9hZzRzfkZdFGAH-fTb6yzv0iD0laaq35Vp3iG6SdYJk2UT7O5Is403Rrk8BY7t53Szs18IzTvBktVCZ2Xr81i9BrK9Z2_PMDr0Ha5rO_7DIxjyTIEpmtv4tCrYPtWXxUFTuVZ9iyaUiETMzS-axo_LJb_QFHTbuO8W1U_-ePKnOxSVEydKJJ-LCROK9KZ3TJ-tLJOPK2kXPRZxtm0T5Wwq-dSszc5pTBGPh6zJfLBN_Hg"
    
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    
    def call_tool(tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call an MCP tool."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            logger.info(f"Calling tool: {tool_name} with args: {arguments}")
            response = requests.post(server_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error(f"Tool error: {result['error']}")
                return None
                
            return result.get('result')
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            return None
    
    logger.info("🧪 Testing EHR MCP Tools with Correct Parameters")
    logger.info("=" * 60)
    
    # Test 1: Get Patient Summary (using 'id' parameter instead of 'patient_id')
    logger.info("\n📋 Test 1: Get Patient Summary")
    result = call_tool("getPatientsIdSummary", {"id": "12873"})
    if result:
        logger.info("✓ Patient Summary Result:")
        logger.info(json.dumps(result, indent=2))
    
    # Test 2: Get Patient Labs (using 'id' parameter)
    logger.info("\n🧪 Test 2: Get Patient Labs")
    result = call_tool("getPatientsIdLabs", {"id": "12873"})
    if result:
        logger.info("✓ Patient Labs Result:")
        logger.info(json.dumps(result, indent=2))
    
    # Test 3: Get Debug Data
    logger.info("\n🔍 Test 3: Get Debug Data")
    result = call_tool("getDebugData", {})
    if result:
        logger.info("✓ Debug Data Result:")
        logger.info(json.dumps(result, indent=2))
    
    # Test 4: Post Medication Order
    logger.info("\n💊 Test 4: Post Medication Order")
    medication_order = {
        "patient_id": "12873",
        "medication": "empagliflozin",
        "dose": "10 mg",
        "frequency": "daily"
    }
    result = call_tool("postOrdersMedication", medication_order)
    if result:
        logger.info("✓ Medication Order Result:")
        logger.info(json.dumps(result, indent=2))
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ EHR MCP Tools Testing Complete")

if __name__ == "__main__":
    test_ehr_tools()