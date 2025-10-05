# WSO2 Ballerina EHR Backend Service - Test Summary

## ✅ Status: Data Available & Ready to Test

Your Ballerina service is properly configured to read from `data.txt` and return patient data.

## 📊 Available Test Data

The `data.txt` file now contains **4 patients** with complete medical records:

### Patient 1: John Doe (ID: 12873)
- **Conditions**: Type 2 Diabetes Mellitus, Hypertension
- **Medications**: Metformin, Lisinopril
- **Labs**: Multiple A1c and eGFR records (latest A1c: 7.2% - abnormal)
- **Status**: Most recent A1c is elevated

### Patient 2: Jane Smith (ID: 12874)
- **Conditions**: Chronic Kidney Disease
- **Medications**: Losartan
- **Labs**: eGFR (45.0 - abnormal), A1c (5.8% - normal)
- **Status**: Abnormal kidney function

### Patient 3: Bob Johnson (ID: 12875)
- **Conditions**: Type 1 Diabetes Mellitus (severe)
- **Medications**: Insulin
- **Labs**: A1c (8.5% - abnormal), eGFR (75.0 - normal)
- **Status**: Poorly controlled diabetes

### Patient 4: Sarah Williams (ID: 12876) ✨ NEW
- **Conditions**: Asthma, Allergic Rhinitis
- **Medications**: Albuterol Inhaler, Fluticasone
- **Labs**: A1c (5.2% - normal), eGFR (95.0 - normal)
- **Status**: All labs normal, well-controlled conditions

---

## 🧪 Quick Test Commands

### Test the API you selected:

```http
GET http://localhost:8001/ehr/patients/12873/summary
```

**Expected Response:**
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
    },
    {
      "problemId": "P002",
      "description": "Hypertension",
      "status": "active",
      "onsetDate": "2019-08-22",
      "severity": "mild"
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
  "lastEgfr": {
    "labId": "L002",
    "name": "eGFR",
    "value": 85.0,
    "unit": "mL/min/1.73m²",
    "referenceRange": ">60",
    "recordDate": "2024-01-10",
    "status": "normal"
  }
}
```

---

## 📋 All Available Endpoints

### 1. GET Patient Summary
```http
GET http://localhost:8001/ehr/patients/{id}/summary
```
Returns complete patient summary including demographics, problems, medications, vitals, and latest A1c/eGFR labs.

**Test with:**
- `12873` - John Doe
- `12874` - Jane Smith
- `12875` - Bob Johnson
- `12876` - Sarah Williams (NEW)

### 2. GET Patient Labs
```http
GET http://localhost:8001/ehr/patients/{id}/labs
GET http://localhost:8001/ehr/patients/{id}/labs?names=A1c
GET http://localhost:8001/ehr/patients/{id}/labs?names=A1c,eGFR
GET http://localhost:8001/ehr/patients/{id}/labs?last_n=2
```
Returns lab results with optional filtering by lab name and limiting results.

### 3. POST Medication Order
```http
POST http://localhost:8001/ehr/orders/medication
Content-Type: application/json

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
Creates a medication order (draft status).

### 4. GET Debug Data
```http
GET http://localhost:8001/ehr/debug/data
```
Returns the entire contents of `data.txt` for debugging.

---

## 🚀 How to Test

### Option 1: Using the HTTP files provided
1. Open `tryit.http` (already updated with test examples)
2. Click on any request to run it
3. View the response in VS Code

### Option 2: Using the comprehensive test file
1. Open `API_TEST_EXAMPLES.http`
2. Contains all test scenarios with documentation
3. Click "Send Request" above each HTTP request

### Option 3: Using curl
```bash
# Get patient summary
curl http://localhost:8001/ehr/patients/12873/summary

# Get labs
curl http://localhost:8001/ehr/patients/12873/labs?names=A1c

# Post medication order
curl -X POST http://localhost:8001/ehr/orders/medication \
  -H "Content-Type: application/json" \
  -d '{
    "patientId": "12873",
    "medicationName": "Atorvastatin",
    "dosage": "20mg",
    "frequency": "once daily",
    "duration": "90 days",
    "prescriberId": "DR-12345"
  }'
```

---

## 📁 Files Updated

1. ✅ `data.txt` - Added 4th patient (Sarah Williams, ID: 12876)
2. ✅ `target/tryit.http` - Updated with additional test examples
3. ✅ `API_TEST_EXAMPLES.http` - Comprehensive test file created

---

## 🔍 Verification

The service reads from `data.txt` properly because:
1. The `loadPatientData()` function in `main.bal` reads from the file
2. The `getPatientById()` function searches the loaded data
3. The `init()` function ensures data is available on startup
4. All endpoints use these functions to fetch data

**Your request is working correctly!** The endpoint reads patient data from `data.txt` and returns it in the response.

---

## 💡 Additional Testing Tips

- **Test non-existent patient**: Try ID `99999` to see error handling
- **Test lab filtering**: Use `names` parameter with different lab names
- **Test ordering**: Create orders for existing and new patients
- **Check data persistence**: Orders are stored in the data file

Enjoy testing your Ballerina EHR Backend Service! 🎉
