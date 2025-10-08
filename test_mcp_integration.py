#!/usr/bin/env python3
"""
Test script to verify MCP integration in both Care Plan and Evidence agents
"""

import json
import requests
import time

def test_care_plan_agent_mcp():
    """Test the care plan agent with MCP integration."""
    print("\n" + "=" * 70)
    print("🧪 Testing Care Plan Agent with MCP Integration")
    print("=" * 70)
    
    url = "http://localhost:8000/care-plan"
    
    payload = {
        "user_id": "test_user_123",
        "patient_id": "12873",
        "question": "What are the best treatment options for this patient?"
    }
    
    print(f"\n📤 Request to: {url}")
    print(f"📝 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        print("\n⏳ Sending request...")
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        print("\n✅ SUCCESS: Care plan generated")
        print("=" * 70)
        print(json.dumps(result, indent=2))
        
        # Check for MCP indicators in response
        print("\n🔍 Checking for MCP integration indicators...")
        if "patient_summary" in result:
            print("  ✓ Patient summary retrieved")
        if "evidence_pack" in result:
            print("  ✓ Evidence pack generated")
        if "plan_card" in result:
            print("  ✓ Care plan created")
            
        return True
        
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out after 60 seconds")
        return False
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text[:500]}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_evidence_agent_mcp():
    """Test the evidence agent with MCP integration."""
    print("\n" + "=" * 70)
    print("🧪 Testing Evidence Agent with MCP Integration")
    print("=" * 70)
    
    url = "http://localhost:8003/agents/evidence/search"
    
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
    
    print(f"\n📤 Request to: {url}")
    print(f"📝 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        print("\n⏳ Sending request...")
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        print("\n✅ SUCCESS: Evidence search completed")
        print("=" * 70)
        print(json.dumps(result, indent=2)[:1000] + "...")
        
        # Check for MCP integration
        evidence_pack = result.get("evidence_pack", {})
        analyses = evidence_pack.get("analyses", [])
        trials = evidence_pack.get("trials", [])
        
        print("\n🔍 Evidence Pack Summary:")
        print(f"  📊 Analyses: {len(analyses)}")
        print(f"  🔬 Trials: {len(trials)}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text[:500]}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("🚀 MCP Integration Test Suite")
    print("=" * 70)
    print("Testing both Care Plan Agent and Evidence Agent with MCP backends")
    print()
    
    results = []
    
    # Test Evidence Agent first (simpler)
    print("\n[1/2] Testing Evidence Agent...")
    time.sleep(1)
    results.append(("Evidence Agent", test_evidence_agent_mcp()))
    
    # Test Care Plan Agent (more complex)
    print("\n[2/2] Testing Care Plan Agent...")
    time.sleep(1)
    results.append(("Care Plan Agent", test_care_plan_agent_mcp()))
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")
    
    all_passed = all(passed for _, passed in results)
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check logs for details.")
    print("=" * 70 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
