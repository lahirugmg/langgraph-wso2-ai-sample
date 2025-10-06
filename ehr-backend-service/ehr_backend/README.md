# EHR Backend Service - Ballerina REST API

A comprehensive Electronic Health Records (EHR) backend service built with WSO2 Ballerina, providing RESTful APIs for managing patient data, lab results, and medication orders.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [API Endpoints](#api-endpoints)
- [Data Model](#data-model)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Configuration](#configuration)

---

## 🎯 Overview

This EHR backend service provides a simple yet powerful API for managing electronic health records. It stores patient data in a JSON file (`data.txt`) and exposes RESTful endpoints for:

- **Patient Summaries**: Retrieve complete patient information including demographics, problems, medications, vitals, and latest lab results
- **Lab Results**: Query and filter patient laboratory test results
- **Medication Orders**: Create medication orders for patients

### Technology Stack

- **Language**: Ballerina (WSO2)
- **Runtime**: Ballerina 2201.x or higher
- **Data Storage**: File-based JSON storage (`data.txt`)
- **Port**: 8001

---

## ✨ Features

- ✅ **Auto-initialization**: Automatically creates `data.txt` with sample data if file doesn't exist
- ✅ **RESTful API**: Clean REST endpoints following best practices
- ✅ **Data Persistence**: File-based storage for easy development and testing
- ✅ **Validation**: Input validation for all POST requests
- ✅ **Error Handling**: Proper HTTP status codes and error messages
- ✅ **Lab Result Filtering**: Query labs by name and limit results
- ✅ **Auto-create Patients**: Automatically creates basic patient records for new patient IDs
- ✅ **OpenAPI Support**: Includes OpenAPI specification (`openapi.yaml`)

---

## 📦 Prerequisites

Before running this service, ensure you have:

- **Ballerina**: Version 2201.x or higher
  ```bash
  bal version
  ```
- **Python 3** (optional, for JSON formatting in tests)

### Installation

If you don't have Ballerina installed:

1. Visit [Ballerina Downloads](https://ballerina.io/downloads/)
2. Download and install for your platform
3. Verify installation: `bal version`

---

## 🚀 Getting Started

### 1. Clone or Navigate to the Project

```bash
cd /path/to/ehr_backend
```

### 2. Run the Service

```bash
bal run
```

The service will:
- Start on `http://localhost:8001`
- Check for `data.txt` file
- Auto-create `data.txt` with sample data if it doesn't exist
- Display initialization messages

### 3. Verify the Service

```bash
curl http://localhost:8001/ehr/patients/12873/summary
```

You should see a JSON response with patient data.

### 4. Stop the Service

Press `Ctrl+C` in the terminal where the service is running.

---

## 🔌 API Endpoints

### Base URL

```
http://localhost:8001/ehr
```

---

### 1. Get Patient Summary

Retrieve a complete patient summary including demographics, problems, medications, vitals, and the latest A1c and eGFR lab results.

**Endpoint:**
```http
GET /patients/{id}/summary
```

**Path Parameters:**
- `id` (string, required): Patient ID

**Response:** `200 OK`
```json
{
  "demographics": {
    "patientId": "12873",
    "firstName": "John",
    "lastName": "Doe",
    "dateOfBirth": "1980-05-15",
    "gender": "Male",
    "address": "123 Main St, Anytown, ST 12345",
    "phone": "(555) 123-4567",
    "email": "john.doe@email.com"
  },
  "problems": [
    {
      "problemId": "P001",
      "description": "Type 2 Diabetes Mellitus",
      "status": "active",
      "onsetDate": "2020-03-15",
      "severity": "moderate"
    }
  ],
  "medications": [...],
  "vitals": [...],
  "lastA1c": {
    "labId": "L001",
    "name": "A1c",
    "value": 7.2,
    "unit": "%",
    "referenceRange": "<7.0",
    "recordDate": "2024-01-10",
    "status": "abnormal"
  },
  "lastEgfr": {...}
}
```

**Error Response:** `404 Not Found`
```json
{
  "error": "patient_not_found",
  "message": "Patient with ID 99999 not found..."
}
```

**Example:**
```bash
curl http://localhost:8001/ehr/patients/12873/summary
```

---

### 2. Get Patient Labs

Retrieve laboratory test results for a patient with optional filtering.

**Endpoint:**
```http
GET /patients/{id}/labs?names={labNames}&last_n={limit}
```

**Path Parameters:**
- `id` (string, required): Patient ID

**Query Parameters:**
- `names` (string, optional): Comma-separated lab names to filter (e.g., "A1c" or "A1c,eGFR")
- `last_n` (integer, optional): Limit to the last N results

**Response:** `200 OK`
```json
{
  "patientId": "12873",
  "labs": [
    {
      "labId": "L001",
      "name": "A1c",
      "value": 7.2,
      "unit": "%",
      "referenceRange": "<7.0",
      "recordDate": "2024-01-10",
      "status": "abnormal"
    }
  ]
}
```

**Examples:**
```bash
# Get all labs
curl http://localhost:8001/ehr/patients/12873/labs

# Get only A1c results
curl "http://localhost:8001/ehr/patients/12873/labs?names=A1c"

# Get A1c and eGFR results
curl "http://localhost:8001/ehr/patients/12873/labs?names=A1c,eGFR"

# Get last 2 lab results
curl "http://localhost:8001/ehr/patients/12873/labs?last_n=2"

# Combine filters: last 3 A1c results
curl "http://localhost:8001/ehr/patients/12873/labs?names=A1c&last_n=3"
```

---

### 3. Create Medication Order

Create a new medication order for a patient. If the patient doesn't exist, a basic patient record will be automatically created.

**Endpoint:**
```http
POST /orders/medication
```

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "patientId": "12873",
  "medicationName": "Atorvastatin",
  "dosage": "20mg",
  "frequency": "once daily",
  "duration": "90 days",
  "prescriberId": "DR-12345",
  "notes": "For cholesterol management"
}
```

**Required Fields:**
- `patientId` (string, non-empty)
- `medicationName` (string, non-empty)
- `dosage` (string, non-empty)
- `frequency` (string, non-empty)
- `duration` (string)
- `prescriberId` (string)

**Optional Fields:**
- `notes` (string)

**Response:** `200 OK`
```json
{
  "orderId": "ORD-12873-20240115123045",
  "status": "draft",
  "message": "draft created"
}
```

**Error Response:** `400 Bad Request`
```json
{
  "error": "validation_error",
  "message": "Missing required fields: patientId, medicationName, dosage, frequency"
}
```

**Examples:**
```bash
# Create order for existing patient
curl -X POST http://localhost:8001/ehr/orders/medication \
  -H "Content-Type: application/json" \
  -d '{
    "patientId": "12873",
    "medicationName": "Atorvastatin",
    "dosage": "20mg",
    "frequency": "once daily",
    "duration": "90 days",
    "prescriberId": "DR-12345",
    "notes": "For cholesterol management"
  }'

# Create order for new patient (auto-creates patient)
curl -X POST http://localhost:8001/ehr/orders/medication \
  -H "Content-Type: application/json" \
  -d '{
    "patientId": "13000",
    "medicationName": "Amoxicillin",
    "dosage": "500mg",
    "frequency": "three times daily",
    "duration": "10 days",
    "prescriberId": "DR-54321",
    "notes": "For bacterial infection"
  }'
```

---

### 4. Debug - View All Data

Debug endpoint to view the entire contents of `data.txt`.

**Endpoint:**
```http
GET /debug/data
```

**Response:** `200 OK`
```json
{
  "patients": [...]
}
```

**Example:**
```bash
curl http://localhost:8001/ehr/debug/data
```

---

## 📊 Data Model

### Patient Record Structure

```json
{
  "demographics": {
    "patientId": "string",
    "firstName": "string",
    "lastName": "string",
    "dateOfBirth": "string (YYYY-MM-DD)",
    "gender": "string",
    "address": "string (optional)",
    "phone": "string (optional)",
    "email": "string (optional)"
  },
  "problems": [
    {
      "problemId": "string",
      "description": "string",
      "status": "string (active|resolved)",
      "onsetDate": "string (optional)",
      "severity": "string (optional)"
    }
  ],
  "medications": [
    {
      "medicationId": "string",
      "name": "string",
      "dosage": "string",
      "frequency": "string",
      "prescribedDate": "string",
      "status": "string (active|discontinued)"
    }
  ],
  "vitals": [
    {
      "recordDate": "string",
      "bloodPressureSystolic": "decimal (optional)",
      "bloodPressureDiastolic": "decimal (optional)",
      "heartRate": "decimal (optional)",
      "temperature": "decimal (optional)",
      "weight": "decimal (optional)",
      "height": "decimal (optional)"
    }
  ],
  "labs": [
    {
      "labId": "string",
      "name": "string",
      "value": "decimal",
      "unit": "string",
      "referenceRange": "string",
      "recordDate": "string",
      "status": "string (normal|abnormal|critical)"
    }
  ]
}
```

---

## 🧪 Testing

### Quick Test Suite

The project includes several test files:

1. **`tryit.http`** - Interactive REST client file (VS Code)
2. **`API_TEST_EXAMPLES.http`** - Comprehensive test examples
3. **`POST_TESTS.md`** - POST request test commands
4. **`QUICK_TEST_GUIDE.md`** - Quick reference guide

### Sample Test Patients

The service comes with pre-loaded sample data:

| Patient ID | Name | Conditions | Notes |
|------------|------|------------|-------|
| 12873 | John Doe | Type 2 Diabetes, Hypertension | Elevated A1c (7.2%) |
| 12874 | Jane Smith | Chronic Kidney Disease | Low eGFR (45.0) |
| 12875 | Bob Johnson | Type 1 Diabetes (severe) | High A1c (8.5%) |
| 12876 | Sarah Williams | Asthma, Allergic Rhinitis | All labs normal |

### Running Tests

#### Option 1: Using VS Code REST Client

1. Open `tryit.http` or `API_TEST_EXAMPLES.http`
2. Click "Send Request" above any HTTP request
3. View results in the response panel

#### Option 2: Using curl

```bash
# Test patient summary
curl http://localhost:8001/ehr/patients/12873/summary | python3 -m json.tool

# Test labs with filtering
curl "http://localhost:8001/ehr/patients/12873/labs?names=A1c" | python3 -m json.tool

# Test medication order
curl -X POST http://localhost:8001/ehr/orders/medication \
  -H "Content-Type: application/json" \
  -d '{
    "patientId": "12873",
    "medicationName": "Aspirin",
    "dosage": "81mg",
    "frequency": "once daily",
    "duration": "ongoing",
    "prescriberId": "DR-12345"
  }' | python3 -m json.tool
```

#### Option 3: Using Postman

Import the OpenAPI specification (`openapi.yaml`) into Postman and test all endpoints.

---

## 📁 Project Structure

```
ehr_backend/
├── README.md                    # This file
├── Ballerina.toml              # Ballerina project configuration
├── Dependencies.toml           # Dependency management
├── main.bal                    # Main service implementation
├── types.bal                   # Type definitions
├── config.bal                  # Configuration (if any)
├── openapi.yaml                # OpenAPI specification
├── data.txt                    # Patient data storage (auto-created)
├── data.txt.backup             # Backup of data file
├── API_TEST_EXAMPLES.http      # Comprehensive test examples
├── POST_TESTS.md               # POST request test documentation
├── POST_TEST_RESULTS.md        # Detailed test results
├── QUICK_TEST_GUIDE.md         # Quick reference for testing
├── TEST_SUMMARY.md             # Overall test summary
└── target/                     # Build artifacts
    ├── bin/
    │   └── ehr_backend.jar     # Compiled JAR
    ├── cache/
    └── tryit.http              # Generated test file
```

---

## ⚙️ Configuration

### Server Configuration

The service runs on port `8001` by default. To change the port, modify `main.bal`:

```ballerina
listener http:Listener ehrListener = new (8001);  // Change port here
```

### Data File Location

Data is stored in `data.txt` in the project root. The file location is configured in `main.bal`:

```ballerina
const string DATA_FILE = "data.txt";  // Change file name here
```

### Sample Data

Sample patients are defined in the `getSamplePatients()` function in `main.bal`. You can customize the initial data by modifying this function.

---

## 🔧 Development

### Building the Project

```bash
bal build
```

The compiled JAR will be in `target/bin/ehr_backend.jar`.

### Running the Compiled JAR

```bash
bal run target/bin/ehr_backend.jar
```

### Code Structure

- **`main.bal`**: Main service implementation with all endpoints
- **`types.bal`**: Type definitions for all data structures
- **`data.txt`**: JSON file storing patient records

### Adding New Endpoints

1. Add the resource function in the service definition in `main.bal`
2. Define any new types in `types.bal`
3. Update the OpenAPI specification in `openapi.yaml`
4. Add test cases to the test files

---

## 🐛 Troubleshooting

### Service Won't Start

**Problem**: Port 8001 is already in use

**Solution**: 
```bash
# Find process using port 8001
lsof -i :8001

# Kill the process
kill -9 <PID>

# Or change the port in main.bal
```

### Data File Issues

**Problem**: `data.txt` is corrupted or has invalid JSON

**Solution**:
```bash
# Delete the file - it will be auto-recreated
rm data.txt

# Restart the service
bal run
```

### Patient Not Found

**Problem**: 404 error when querying patient

**Solution**:
- Check if patient ID exists: `curl http://localhost:8001/ehr/debug/data`
- Verify the `data.txt` file has valid JSON
- Check the patient ID spelling/format

---

## 📝 API Response Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success - Request completed successfully |
| 400 | Bad Request - Invalid input or missing required fields |
| 404 | Not Found - Patient or resource not found |
| 500 | Internal Server Error - Server-side error |

---

## 🔐 Security Considerations

**Note**: This is a development/demo service. For production use, consider:

- ✅ Add authentication/authorization (OAuth2, JWT)
- ✅ Use a proper database instead of file storage
- ✅ Add HTTPS/TLS encryption
- ✅ Implement rate limiting
- ✅ Add input sanitization
- ✅ Implement audit logging
- ✅ Add CORS configuration if needed

---

## 📚 Additional Resources

- [Ballerina Documentation](https://ballerina.io/learn/)
- [Ballerina HTTP Module](https://lib.ballerina.io/ballerina/http/latest)
- [RESTful API Design Best Practices](https://restfulapi.net/)

---

## 📄 License

This project is provided as-is for educational and demonstration purposes.

---

## 👥 Contributing

For questions or contributions, please contact the development team.

---

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the test files for examples
3. Check Ballerina logs in the terminal

---

**Built with ❤️ using WSO2 Ballerina**
