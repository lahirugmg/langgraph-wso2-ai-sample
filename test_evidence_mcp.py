#!/usr/bin/env python3
"""
Test the MCP Evidence Agent
"""

import json
import requests

def test_evidence_search():
    """Test the evidence search endpoint with MCP integration."""
    
    url = "http://localhost:8005/agents/evidence/search"
    
    # Test payload
    payload = {
        "age": 68,
        "diagnosis": "Type 2 diabetes mellitus with chronic kidney disease",
        "egfr": 45.2,
        "comorbidities": ["hypertension", "dyslipidemia"],
        "geo": {
            "lat": 35.15,
            "lon": -90.05,
            "radius_km": 30
        }
    }
    
    print("🧪 Testing MCP Evidence Agent")
    print("=" * 50)
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        print("✅ SUCCESS: Evidence search completed")
        print("=" * 50)
        print(json.dumps(result, indent=2))
        
        # Check for MCP integration indicators
        evidence_pack = result.get("evidence_pack", {})
        mcp_enabled = evidence_pack.get("mcp_enabled", False)
        data_sources = evidence_pack.get("data_sources", {})
        
        print()
        print("🔍 MCP Integration Status:")
        print(f"  MCP Enabled: {mcp_enabled}")
        print(f"  EHR MCP: {data_sources.get('ehr_mcp', False)}")
        print(f"  Trial MCP: {data_sources.get('trial_mcp', False)}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_evidence_search()