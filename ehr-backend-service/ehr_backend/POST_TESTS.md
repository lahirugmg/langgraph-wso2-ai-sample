# 🚀 POST Request Test Commands - Ready to Use

## ✅ All Tests Passed! Copy & Run These Commands:

---

## 1️⃣ Create Order for Existing Patient (John Doe - 12873)
```bash
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
  }' | python3 -m json.tool
```

**Expected Response:**
```json
{
    "orderId": "ORD-12873-20240115123045",
    "status": "draft",
    "message": "draft created"
}
```

---

## 2️⃣ Create Order for Sarah Williams (12876)
```bash
curl -X POST http://localhost:8001/ehr/orders/medication \
  -H "Content-Type: application/json" \
  -d '{
    "patientId": "12876",
    "medicationName": "Montelukast",
    "dosage": "10mg",
    "frequency": "once daily at bedtime",
    "duration": "30 days",
    "prescriberId": "DR-67890",
    "notes": "Additional asthma control medication"
  }' | python3 -m json.tool
```

---

## 3️⃣ Create Order for New Patient (Auto-creates patient record)
```bash
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
  }' | python3 -m json.tool
```

**Then verify patient was created:**
```bash
curl http://localhost:8001/ehr/patients/13000/summary | python3 -m json.tool
```

---

## 4️⃣ Test Validation Error (Missing Medication Name)
```bash
curl -X POST http://localhost:8001/ehr/orders/medication \
  -H "Content-Type: application/json" \
  -d '{
    "patientId": "12873",
    "medicationName": "",
    "dosage": "20mg",
    "frequency": "once daily",
    "duration": "90 days",
    "prescriberId": "DR-12345"
  }' | python3 -m json.tool
```

**Expected Error:**
```json
{
    "error": "validation_error",
    "message": "Missing required fields: patientId, medicationName, dosage, frequency"
}
```

---

## 5️⃣ Test Validation Error (Empty Patient ID)
```bash
curl -X POST http://localhost:8001/ehr/orders/medication \
  -H "Content-Type: application/json" \
  -d '{
    "patientId": "",
    "medicationName": "Aspirin",
    "dosage": "81mg",
    "frequency": "once daily",
    "duration": "ongoing",
    "prescriberId": "DR-12345"
  }' | python3 -m json.tool
```

---

## 🎯 Quick Test - All at Once

Run all successful tests:
```bash
echo "=== Test 1: Existing Patient 12873 ==="
curl -X POST http://localhost:8001/ehr/orders/medication \
  -H "Content-Type: application/json" \
  -d '{"patientId":"12873","medicationName":"Atorvastatin","dosage":"20mg","frequency":"once daily","duration":"90 days","prescriberId":"DR-12345","notes":"For cholesterol"}' | python3 -m json.tool

echo -e "\n=== Test 2: Existing Patient 12876 ==="
curl -X POST http://localhost:8001/ehr/orders/medication \
  -H "Content-Type: application/json" \
  -d '{"patientId":"12876","medicationName":"Montelukast","dosage":"10mg","frequency":"once daily","duration":"30 days","prescriberId":"DR-67890"}' | python3 -m json.tool

echo -e "\n=== Test 3: New Patient 13001 ==="
curl -X POST http://localhost:8001/ehr/orders/medication \
  -H "Content-Type: application/json" \
  -d '{"patientId":"13001","medicationName":"Ibuprofen","dosage":"400mg","frequency":"as needed","duration":"30 days","prescriberId":"DR-11111"}' | python3 -m json.tool
```

---

## 📊 Test Results Summary

| Test | Patient ID | Status | Result |
|------|-----------|--------|--------|
| ✅ 1 | 12873 (John Doe) | Success | Order created |
| ✅ 2 | 12876 (Sarah Williams) | Success | Order created |
| ✅ 3 | 12999 (New) | Success | Patient + Order created |
| ✅ 4 | 12873 (Invalid) | Error | Validation working |
| ✅ 5 | Empty ID | Error | Validation working |

---

## 💡 Key Features Verified

✅ **Creates orders** for existing patients  
✅ **Auto-creates patients** if they don't exist  
✅ **Validates required fields** (patientId, medicationName, dosage, frequency)  
✅ **Returns proper errors** for invalid input  
✅ **Generates unique order IDs** in format `ORD-{patientId}-{timestamp}`  

---

## 🎉 All POST Tests Successful!

Your Ballerina service is handling POST requests correctly! 

See **POST_TEST_RESULTS.md** for detailed test results.
