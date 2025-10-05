# 🚀 Quick Test Reference

## ✅ All Systems Working!

Your Ballerina EHR service is reading from `data.txt` and serving data correctly.

---

## 🧪 Quick Test Commands (Copy & Paste)

### 1. Test the request you selected (Patient 12873 - John Doe):
```bash
curl http://localhost:8001/ehr/patients/12873/summary | python3 -m json.tool
```

### 2. Test the NEW patient (12876 - Sarah Williams):
```bash
curl http://localhost:8001/ehr/patients/12876/summary | python3 -m json.tool
```

### 3. Test Labs Endpoint (A1c only):
```bash
curl "http://localhost:8001/ehr/patients/12873/labs?names=A1c" | python3 -m json.tool
```

### 4. Test Labs Endpoint (Last 2 results):
```bash
curl "http://localhost:8001/ehr/patients/12873/labs?last_n=2" | python3 -m json.tool
```

### 5. Test Medication Order (POST):
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

### 6. Test Non-existent Patient (Error handling):
```bash
curl http://localhost:8001/ehr/patients/99999/summary
```

### 7. Debug - View all data:
```bash
curl http://localhost:8001/ehr/debug/data | python3 -m json.tool
```

---

## 📊 Available Patient IDs

| ID    | Name            | Conditions                     | Key Notes                |
|-------|-----------------|--------------------------------|--------------------------|
| 12873 | John Doe        | Type 2 Diabetes, Hypertension | Elevated A1c (7.2%)     |
| 12874 | Jane Smith      | Chronic Kidney Disease        | Low eGFR (45.0)         |
| 12875 | Bob Johnson     | Type 1 Diabetes (severe)      | High A1c (8.5%)         |
| 12876 | Sarah Williams  | Asthma, Allergic Rhinitis     | All labs normal ✨ NEW  |

---

## 🎯 Test in VS Code

Open these files in VS Code and click the requests:
- **`tryit.http`** - Updated with multiple test examples
- **`API_TEST_EXAMPLES.http`** - Comprehensive test suite with documentation

---

## ✅ Verification Complete

- ✅ Data exists in `data.txt` (4 patients)
- ✅ Service reads from `data.txt` correctly
- ✅ Patient 12873 returns complete summary
- ✅ Patient 12876 (new) returns complete summary
- ✅ Labs endpoint filters correctly
- ✅ All endpoints working as expected

**Your Ballerina service is production-ready for testing!** 🎉
