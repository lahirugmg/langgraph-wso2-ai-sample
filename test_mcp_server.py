#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Server Test Script

This script tests the connection to the EHR MCP server using the provided configuration.
It demonstrates how to:
1. Connect to the MCP server
2. List available tools/resources
3. Call MCP tools
4. Test the server's capabilities
"""

import json
import logging
import requests
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, server_url: str, auth_token: str):
        """Initialize MCP client with server URL and authentication token."""
        self.server_url = server_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
        
    def initialize(self) -> Optional[Dict[str, Any]]:
        """Initialize connection with the MCP server."""
        logger.info(f"Initializing connection to MCP server: {self.server_url}")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {
                        "listChanged": True
                    },
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "EHR-MCP-Test-Client",
                    "version": "1.0.0"
                }
            }
        }
        
        try:
            response = requests.post(
                self.server_url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error(f"MCP initialization error: {result['error']}")
                return None
                
            logger.info("✓ MCP server initialized successfully")
            logger.info(f"Server capabilities: {json.dumps(result.get('result', {}), indent=2)}")
            return result.get('result')
            
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to initialize MCP server: {e}")
            return None
    
    def list_tools(self) -> Optional[List[Dict[str, Any]]]:
        """List available tools from the MCP server."""
        logger.info("Listing available tools...")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        try:
            response = requests.post(
                self.server_url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error(f"Error listing tools: {result['error']}")
                return None
                
            tools = result.get('result', {}).get('tools', [])
            logger.info(f"✓ Found {len(tools)} available tools:")
            for tool in tools:
                logger.info(f"  - {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
            
            return tools
            
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to list tools: {e}")
            return None
    
    def list_resources(self) -> Optional[List[Dict[str, Any]]]:
        """List available resources from the MCP server."""
        logger.info("Listing available resources...")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list",
            "params": {}
        }
        
        try:
            response = requests.post(
                self.server_url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error(f"Error listing resources: {result['error']}")
                return None
                
            resources = result.get('result', {}).get('resources', [])
            logger.info(f"✓ Found {len(resources)} available resources:")
            for resource in resources:
                logger.info(f"  - {resource.get('uri', 'Unknown')}: {resource.get('name', 'No name')}")
            
            return resources
            
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to list resources: {e}")
            return None
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call a specific tool with given arguments."""
        logger.info(f"Calling tool '{tool_name}' with arguments: {arguments}")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            response = requests.post(
                self.server_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error(f"Error calling tool '{tool_name}': {result['error']}")
                return None
                
            logger.info(f"✓ Tool '{tool_name}' executed successfully")
            return result.get('result')
            
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to call tool '{tool_name}': {e}")
            return None
    
    def read_resource(self, uri: str) -> Optional[Dict[str, Any]]:
        """Read a specific resource."""
        logger.info(f"Reading resource: {uri}")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {
                "uri": uri
            }
        }
        
        try:
            response = requests.post(
                self.server_url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error(f"Error reading resource '{uri}': {result['error']}")
                return None
                
            logger.info(f"✓ Resource '{uri}' read successfully")
            return result.get('result')
            
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to read resource '{uri}': {e}")
            return None

def test_ehr_mcp_server():
    """Test the EHR MCP server with the provided configuration."""
    
    # Configuration from the user's request
    server_url = "https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.bijiraapis.dev/clinicagent/ehr-mcp/v1.0/mcp"
    auth_token = "eyJ4NXQjUzI1NiI6ImVmalpEVEE4ZXFUbTMwYUE4LW1wNTFya2x1NnlhcW52UzZWZW92U3hRVHMiLCJraWQiOiI4OTBkZGZhNS00YTQwLTQ1OTQtYTFjMy04YWRlOGQwM2IzMWEjNmQwODNhZmYtMWMyYy00ODJiLWJlZGEtYzkyNjQzNjcyMjkwIiwiYWxnIjoiUlMyNTYifQ.eyJzdWIiOiJscTNEeHpGU1lURFRpZ2hsT3ZMa0tyUGM3VnBHIiwiYXVkIjoibHEzRHh6RlNZVERUaWdobE92TGtLclBjN1ZwRyIsImF1dCI6IkFQUExJQ0FUSU9OIiwibmJmIjoxNzU5OTQwOTg3LCJhenAiOiJscTNEeHpGU1lURFRpZ2hsT3ZMa0tyUGM3VnBHIiwib3JnYW5pemF0aW9uIjp7InV1aWQiOiI4OTBkZGZhNS00YTQwLTQ1OTQtYTFjMy04YWRlOGQwM2IzMWEifSwic2NvcGUiOiIiLCJpc3MiOiJodHRwczovLzg5MGRkZmE1LTRhNDAtNDU5NC1hMWMzLThhZGU4ZDAzYjMxYS1wcm9kLmUxLXVzLWVhc3QtYXp1cmUuY2hvcmVvc3RzLmRldi9vYXV0aDIvdG9rZW4iLCJleHAiOjE3NjA5NDA5NDcsImlhdCI6MTc1OTk0MDk4NywianRpIjoiNjdiOTEwMzEtYzc5YS00NGUyLWFjYjEtNmY4MWI1OWFkNGQ2In0.PeY8m4YAkWXy38ErhZ71LWFZNjJUjabSK1AwGTvPVvCSwofaGc1aa2s1QreqOnW07IhzKBGWropEveBV9X8Q8sc15bBCM8Jyd2pX3KhjQ9hZzRzfkZdFGAH-fTb6yzv0iD0laaq35Vp3iG6SdYJk2UT7O5Is403Rrk8BY7t53Szs18IzTvBktVCZ2Xr81i9BrK9Z2_PMDr0Ha5rO_7DIxjyTIEpmtv4tCrYPtWXxUFTuVZ9iyaUiETMzS-axo_LJb_QFHTbuO8W1U_-ePKnOxSVEydKJJ-LCROK9KZ3TJ-tLJOPK2kXPRZxtm0T5Wwq-dSszc5pTBGPh6zJfLBN_Hg"
    
    logger.info("=" * 60)
    logger.info("🚀 Starting EHR MCP Server Test")
    logger.info("=" * 60)
    
    # Initialize MCP client
    client = MCPClient(server_url, auth_token)
    
    # Test 1: Initialize connection
    logger.info("\n📋 Test 1: Initialize MCP Server Connection")
    init_result = client.initialize()
    if not init_result:
        logger.error("❌ Failed to initialize MCP server. Stopping tests.")
        return
    
    # Test 2: List available tools
    logger.info("\n🔧 Test 2: List Available Tools")
    tools = client.list_tools()
    
    # Test 3: List available resources
    logger.info("\n📚 Test 3: List Available Resources")
    resources = client.list_resources()
    
    # Test 4: Test tool calls (if tools are available)
    if tools:
        logger.info("\n⚡ Test 4: Test Tool Calls")
        
        # Example: Test getting patient summary (common EHR operation)
        for tool in tools:
            tool_name = tool.get('name', '')
            if 'patient' in tool_name.lower() or 'summary' in tool_name.lower():
                logger.info(f"Testing tool: {tool_name}")
                result = client.call_tool(tool_name, {"patient_id": "12873"})
                if result:
                    logger.info(f"Tool result: {json.dumps(result, indent=2)}")
                break
        else:
            # Try the first available tool with basic parameters
            if tools:
                first_tool = tools[0]
                tool_name = first_tool.get('name', '')
                logger.info(f"Testing first available tool: {tool_name}")
                result = client.call_tool(tool_name, {})
                if result:
                    logger.info(f"Tool result: {json.dumps(result, indent=2)}")
    
    # Test 5: Test resource reading (if resources are available)
    if resources:
        logger.info("\n📖 Test 5: Test Resource Reading")
        first_resource = resources[0]
        resource_uri = first_resource.get('uri', '')
        if resource_uri:
            result = client.read_resource(resource_uri)
            if result:
                logger.info(f"Resource content: {json.dumps(result, indent=2)}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ MCP Server Testing Complete")
    logger.info("=" * 60)

def test_oauth_token():
    """Test if the OAuth token is still valid by making a simple request."""
    logger.info("\n🔐 Testing OAuth Token Validity")
    
    # Use the token endpoint to validate
    token_endpoint = "https://890ddfa5-4a40-4594-a1c3-8ade8d03b31a-prod.e1-us-east-azure.choreosts.dev/oauth2/token"
    client_id = "lq3DxzFSYTDTighlOvLkKrPc7VpG"
    client_secret = "cm4lMNG7teYcZPVlS8PWE2GmpwL0"
    
    try:
        response = requests.post(
            token_endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        response.raise_for_status()
        token_data = response.json()
        
        logger.info("✓ OAuth token endpoint is accessible")
        logger.info(f"✓ New token obtained (expires in {token_data.get('expires_in', 'unknown')} seconds)")
        return token_data.get('access_token')
        
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Failed to validate OAuth token: {e}")
        return None

if __name__ == "__main__":
    # First test OAuth token validity
    test_oauth_token()
    
    # Then test MCP server
    test_ehr_mcp_server()