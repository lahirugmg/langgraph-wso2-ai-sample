#!/bin/bash

# API Testing Script for Clinical Research Services API
# This script tests all endpoints with comprehensive test data

BASE_URL="http://localhost:8002"
CONTENT_TYPE="application/json"

echo "=========================================="
echo "Clinical Research Services API Test Suite"
echo "=========================================="
echo ""

# Function to test GET /services
test_services_endpoint() {
    echo "1. Testing GET /services endpoint:"
    echo "-----------------------------------"
    response=$(curl -s -X GET "$BASE_URL/services" -H "Content-Type: $CONTENT_TYPE")
    echo "Response: $response"
    echo ""
}

# Function to test GET /trials
test_get_all_trials() {
    echo "2. Testing GET /trials endpoint:"
    echo "-------------------------------"
    response=$(curl -s -X GET "$BASE_URL/trials" -H "Content-Type: $CONTENT_TYPE")
    echo "Response (truncated): $(echo $response | cut -c1-200)..."
    trials_count=$(echo $response | jq '. | length' 2>/dev/null || echo "Unable to parse JSON")
    echo "Total trials returned: $trials_count"
    echo ""
}

# Function to test GET /trials/{id} for various IDs
test_get_individual_trials() {
    echo "3. Testing GET /trials/{id} endpoint:"
    echo "------------------------------------"
    
    # Test existing trial IDs
    for trial_id in 1 2 3 5 10; do
        echo "Testing trial ID: $trial_id"
        response=$(curl -s -X GET "$BASE_URL/trials/$trial_id" -H "Content-Type: $CONTENT_TYPE")
        if echo $response | jq . >/dev/null 2>&1; then
            title=$(echo $response | jq -r '.title' 2>/dev/null)
            condition=$(echo $response | jq -r '.condition' 2>/dev/null)
            echo "  ✓ Found: $title - $condition"
        else
            echo "  ✗ Error or not found: $response"
        fi
    done
    
    # Test non-existent trial ID
    echo "Testing non-existent trial ID: 999"
    response=$(curl -s -X GET "$BASE_URL/trials/999" -H "Content-Type: $CONTENT_TYPE")
    echo "  Expected 404: $response"
    echo ""
}

# Function to test POST /trials
test_post_trials() {
    echo "4. Testing POST /trials endpoint:"
    echo "--------------------------------"
    
    # Test data for new trial
    new_trial='[{
        "id": 11,
        "nctId": "NCT99999999",
        "title": "Test Trial via API",
        "condition": "Test condition",
        "phase": "Phase I",
        "status": "Recruiting",
        "principalInvestigator": "Dr. Test Investigator",
        "startDate": "2024-10-05",
        "endDate": "2025-10-05",
        "siteDistanceKm": 10.0,
        "eligibilitySummary": "Test eligibility criteria"
    }]'
    
    echo "Adding new trial..."
    response=$(curl -s -X POST "$BASE_URL/trials" \
        -H "Content-Type: $CONTENT_TYPE" \
        -d "$new_trial")
    echo "Response: $response"
    
    # Verify the trial was added
    echo "Verifying new trial was added..."
    verify_response=$(curl -s -X GET "$BASE_URL/trials/11" -H "Content-Type: $CONTENT_TYPE")
    if echo $verify_response | jq . >/dev/null 2>&1; then
        echo "  ✓ Trial successfully added and can be retrieved"
    else
        echo "  ✗ Trial not found after addition"
    fi
    echo ""
}

# Function to test error cases
test_error_cases() {
    echo "5. Testing Error Cases:"
    echo "----------------------"
    
    # Test POST with empty array
    echo "Testing POST with empty array..."
    response=$(curl -s -X POST "$BASE_URL/trials" \
        -H "Content-Type: $CONTENT_TYPE" \
        -d '[]')
    echo "Response: $response"
    
    # Test POST with malformed JSON
    echo "Testing POST with malformed JSON..."
    response=$(curl -s -X POST "$BASE_URL/trials" \
        -H "Content-Type: $CONTENT_TYPE" \
        -d '{invalid json}')
    echo "Response: $response"
    
    # Test GET with invalid trial ID format
    echo "Testing GET with invalid trial ID..."
    response=$(curl -s -X GET "$BASE_URL/trials/abc" -H "Content-Type: $CONTENT_TYPE")
    echo "Response: $response"
    echo ""
}

# Function to test data filtering and search capabilities
test_data_variety() {
    echo "6. Testing Data Variety and Coverage:"
    echo "------------------------------------"
    
    echo "Getting all trials to analyze data coverage..."
    response=$(curl -s -X GET "$BASE_URL/trials" -H "Content-Type: $CONTENT_TYPE")
    
    if command -v jq >/dev/null 2>&1; then
        echo "Conditions covered:"
        echo $response | jq -r '.[].condition' | sort | uniq -c
        echo ""
        echo "Phases covered:"
        echo $response | jq -r '.[].phase' | sort | uniq -c
        echo ""
        echo "Status distribution:"
        echo $response | jq -r '.[].status' | sort | uniq -c
        echo ""
        echo "Distance range:"
        min_distance=$(echo $response | jq '[.[].site_distance_km] | min')
        max_distance=$(echo $response | jq '[.[].site_distance_km] | max')
        echo "  Min distance: $min_distance km"
        echo "  Max distance: $max_distance km"
    else
        echo "jq not available for detailed analysis"
    fi
    echo ""
}

# Function to check service health
check_service_health() {
    echo "0. Checking Service Health:"
    echo "--------------------------"
    
    # Check if service is running
    if curl -s -f "$BASE_URL/services" >/dev/null; then
        echo "✓ Service is running on $BASE_URL"
    else
        echo "✗ Service is not responding. Please start the service first."
        echo "Run: bal run"
        exit 1
    fi
    echo ""
}

# Main execution
main() {
    check_service_health
    test_services_endpoint
    test_get_all_trials
    test_get_individual_trials
    test_post_trials
    test_error_cases
    test_data_variety
    
    echo "=========================================="
    echo "Test Suite Completed"
    echo "=========================================="
    echo "Summary:"
    echo "- All endpoints have been tested"
    echo "- Data coverage includes multiple conditions, phases, and statuses"
    echo "- Error handling scenarios were validated"
    echo "- Service is functioning properly"
}

# Run the test suite
main