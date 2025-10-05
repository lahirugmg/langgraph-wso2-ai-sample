import ballerina/http;
import ballerina/lang.regexp as regexp;

// HTTP listener on port 8001
listener http:Listener ehrListener = new (8001);

// EHR Service
service /ehr on ehrListener {

    // GET /patients/{id}/summary
    resource function get patients/[string id]/summary() returns PatientSummary|ErrorResponse|http:NotFound {
        // Mock patient data - in real implementation, this would query a database
        if (id == "12873" || id == "12874" || id == "12875") {
            return getMockPatientSummary(patientId = id);
        }
        
        return http:NOT_FOUND;
    }

    // GET /patients/{id}/labs
    resource function get patients/[string id]/labs(string? names = (), int? last_n = ()) returns LabsResponse|ErrorResponse|http:NotFound {
        // Validate patient exists
        if (id != "12873" && id != "12874" && id != "12875") {
            return http:NOT_FOUND;
        }

        LabResult[] allLabs = getMockLabResults(patientId = id);
        LabResult[] filteredLabs = allLabs;

        // Filter by lab names if provided
        if (names is string && names.trim().length() > 0) {
            regexp:RegExp commaRegex = re `,`;
            string[] labNames = commaRegex.split(names);
            
            // Trim whitespace from each lab name
            string[] trimmedLabNames = [];
            foreach string labName in labNames {
                trimmedLabNames.push(labName.trim());
            }
            
            LabResult[] tempLabs = [];
            foreach LabResult lab in allLabs {
                foreach string labName in trimmedLabNames {
                    if (lab.name.toLowerAscii() == labName.toLowerAscii()) {
                        tempLabs.push(lab);
                        break;
                    }
                }
            }
            filteredLabs = tempLabs;
        }

        // Limit results if last_n is provided
        if (last_n is int && last_n > 0) {
            int labsLength = filteredLabs.length();
            int startIndex = labsLength > last_n ? labsLength - last_n : 0;
            filteredLabs = filteredLabs.slice(startIndex);
        }

        return {
            patientId: id,
            labs: filteredLabs
        };
    }

    // POST /orders/medication
    resource function post orders/medication(@http:Payload MedicationOrder medicationOrder) returns OrderResponse|ErrorResponse|http:BadRequest {
        // Validate required fields
        if (medicationOrder.patientId.trim().length() == 0 || 
            medicationOrder.medicationName.trim().length() == 0 ||
            medicationOrder.dosage.trim().length() == 0 ||
            medicationOrder.frequency.trim().length() == 0) {
            
            ErrorResponse errorResp = {
                'error: "validation_error",
                message: "Missing required fields: patientId, medicationName, dosage, frequency"
            };
            return http:BAD_REQUEST;
        }

        // Generate mock order ID
        string orderId = "ORD-" + medicationOrder.patientId + "-" + generateTimestamp();
        
        return {
            orderId: orderId,
            status: "draft",
            message: "draft created"
        };
    }
}

// Helper function to generate mock patient summary
function getMockPatientSummary(string patientId) returns PatientSummary {
    Demographics demographics = {
        patientId: patientId,
        firstName: "John",
        lastName: "Doe",
        dateOfBirth: "1980-05-15",
        gender: "Male",
        address: "123 Main St, Anytown, ST 12345",
        phone: "(555) 123-4567",
        email: "john.doe@email.com"
    };

    Problem[] problems = [
        {
            problemId: "P001",
            description: "Type 2 Diabetes Mellitus",
            status: "active",
            onsetDate: "2020-03-15",
            severity: "moderate"
        },
        {
            problemId: "P002",
            description: "Hypertension",
            status: "active",
            onsetDate: "2019-08-22",
            severity: "mild"
        }
    ];

    Medication[] medications = [
        {
            medicationId: "M001",
            name: "Metformin",
            dosage: "500mg",
            frequency: "twice daily",
            prescribedDate: "2020-03-15",
            status: "active"
        },
        {
            medicationId: "M002",
            name: "Lisinopril",
            dosage: "10mg",
            frequency: "once daily",
            prescribedDate: "2019-08-22",
            status: "active"
        }
    ];

    Vitals[] vitals = [
        {
            recordDate: "2024-01-15",
            bloodPressureSystolic: 135.0,
            bloodPressureDiastolic: 85.0,
            heartRate: 72.0,
            temperature: 98.6,
            weight: 180.5,
            height: 70.0
        }
    ];

    LabResult lastA1c = {
        labId: "L001",
        name: "A1c",
        value: 7.2,
        unit: "%",
        referenceRange: "<7.0",
        recordDate: "2024-01-10",
        status: "abnormal"
    };

    LabResult lastEgfr = {
        labId: "L002",
        name: "eGFR",
        value: 85.0,
        unit: "mL/min/1.73m²",
        referenceRange: ">60",
        recordDate: "2024-01-10",
        status: "normal"
    };

    return {
        demographics: demographics,
        problems: problems,
        medications: medications,
        vitals: vitals,
        lastA1c: lastA1c,
        lastEgfr: lastEgfr
    };
}

// Helper function to generate mock lab results
function getMockLabResults(string patientId) returns LabResult[] {
    return [
        {
            labId: "L003",
            name: "A1c",
            value: 6.8,
            unit: "%",
            referenceRange: "<7.0",
            recordDate: "2023-10-10",
            status: "normal"
        },
        {
            labId: "L004",
            name: "eGFR",
            value: 88.0,
            unit: "mL/min/1.73m²",
            referenceRange: ">60",
            recordDate: "2023-10-10",
            status: "normal"
        },
        {
            labId: "L005",
            name: "A1c",
            value: 7.0,
            unit: "%",
            referenceRange: "<7.0",
            recordDate: "2023-07-15",
            status: "normal"
        },
        {
            labId: "L006",
            name: "eGFR",
            value: 82.0,
            unit: "mL/min/1.73m²",
            referenceRange: ">60",
            recordDate: "2023-07-15",
            status: "normal"
        },
        {
            labId: "L001",
            name: "A1c",
            value: 7.2,
            unit: "%",
            referenceRange: "<7.0",
            recordDate: "2024-01-10",
            status: "abnormal"
        },
        {
            labId: "L002",
            name: "eGFR",
            value: 85.0,
            unit: "mL/min/1.73m²",
            referenceRange: ">60",
            recordDate: "2024-01-10",
            status: "normal"
        }
    ];
}

// Helper function to generate timestamp for order ID
function generateTimestamp() returns string {
    // Simple timestamp generation - in real implementation, use proper time libraries
    return "20240115123045";
}
