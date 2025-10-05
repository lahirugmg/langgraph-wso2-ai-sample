import ballerina/http;
import ballerina/io;
import ballerina/lang.regexp as regexp;

// HTTP listener on port 8001
listener http:Listener ehrListener = new (8001);

// File path for patient database
const string DATA_FILE = "data.txt";

// EHR Service
service /ehr on ehrListener {

    // GET /patients/{id}/summary
    resource function get patients/[string id]/summary() returns PatientSummary|ErrorResponse|http:NotFound {
        PatientRecord|error patientResult = getPatientById(patientId = id);
        
        if (patientResult is error) {
            // Log the actual error for debugging
            ErrorResponse errorResp = {
                'error: "patient_not_found",
                message: "Patient with ID " + id + " not found. Error: " + patientResult.message()
            };
            return http:NOT_FOUND;
        }
        
        PatientRecord patientRecord = patientResult;
        
        // Find last A1c and eGFR from labs
        LabResult? lastA1c = findLatestLab(labs = patientRecord.labs, labName = "A1c");
        LabResult? lastEgfr = findLatestLab(labs = patientRecord.labs, labName = "eGFR");
        
        return {
            demographics: patientRecord.demographics,
            problems: patientRecord.problems,
            medications: patientRecord.medications,
            vitals: patientRecord.vitals,
            lastA1c: lastA1c,
            lastEgfr: lastEgfr
        };
    }

    // GET /patients/{id}/labs
    resource function get patients/[string id]/labs(string? names = (), int? last_n = ()) returns LabsResponse|ErrorResponse|http:NotFound {
        PatientRecord|error patientResult = getPatientById(patientId = id);
        
        if (patientResult is error) {
            return http:NOT_FOUND;
        }
        
        PatientRecord patientRecord = patientResult;
        LabResult[] filteredLabs = patientRecord.labs;

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
            foreach LabResult lab in patientRecord.labs {
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
            return errorResp;
        }

        // Check if patient exists, if not create a basic patient record
        PatientRecord|error patientResult = getPatientById(patientId = medicationOrder.patientId);
        
        if (patientResult is error) {
            // Create new patient with basic information
            PatientRecord newPatient = createBasicPatient(patientId = medicationOrder.patientId);
            error? saveResult = savePatient(patient = newPatient);
            
            if (saveResult is error) {
                ErrorResponse errorResp = {
                    'error: "database_error",
                    message: "Failed to create patient record"
                };
                return errorResp;
            }
        }

        // Generate mock order ID
        string orderId = "ORD-" + medicationOrder.patientId + "-" + generateTimestamp();
        
        return {
            orderId: orderId,
            status: "draft",
            message: "draft created"
        };
    }

    // Debug endpoint to check data file contents
    resource function get debug/data() returns json|ErrorResponse {
        string|error fileContent = io:fileReadString(DATA_FILE);
        
        if (fileContent is error) {
            ErrorResponse errorResp = {
                'error: "file_read_error",
                message: "Could not read data file: " + fileContent.message()
            };
            return errorResp;
        }
        
        json|error jsonContent = fileContent.fromJsonString();
        
        if (jsonContent is error) {
            ErrorResponse errorResp = {
                'error: "json_parse_error",
                message: "Could not parse JSON: " + jsonContent.message()
            };
            return errorResp;
        }
        
        return jsonContent;
    }
}

// Initialize data file with sample data if it doesn't exist
function initializeDataFile() {
    // Check if file exists by trying to read it
    string|io:Error fileContent = io:fileReadString(DATA_FILE);
    
    // If file doesn't exist or is empty, create it with sample data
    if (fileContent is io:Error || fileContent.trim().length() == 0) {
        io:println("INFO: data.txt not found or empty. Creating file with sample data...");
        
        PatientData initialData = {
            patients: getSamplePatients()
        };
        
        string dataJson = initialData.toJsonString();
        io:Error? writeResult = io:fileWriteString(DATA_FILE, dataJson);
        
        if (writeResult is io:Error) {
            io:println("ERROR: Failed to create data.txt: " + writeResult.message());
        } else {
            io:println("SUCCESS: data.txt created with " + initialData.patients.length().toString() + " sample patients");
        }
    } else {
        io:println("INFO: data.txt exists. Loading existing patient data...");
    }
}

// Load all patient data from file
function loadPatientData() returns PatientData|error {
    string fileContent = check io:fileReadString(DATA_FILE);
    
    if (fileContent.trim().length() == 0) {
        return {patients: []};
    }
    
    json dataJson = check fileContent.fromJsonString();
    PatientData patientData = check dataJson.cloneWithType(PatientData);
    
    return patientData;
}

// Save all patient data to file
function savePatientData(PatientData data) returns error? {
    string dataJson = data.toJsonString();
    check io:fileWriteString(DATA_FILE, dataJson);
}

// Get patient by ID with better error handling
function getPatientById(string patientId) returns PatientRecord|error {
    PatientData|error dataResult = loadPatientData();
    
    if (dataResult is error) {
        return error("Failed to load patient data: " + dataResult.message());
    }
    
    PatientData data = dataResult;
    
    foreach PatientRecord patient in data.patients {
        if (patient.demographics.patientId == patientId) {
            return patient;
        }
    }
    
    return error("Patient with ID " + patientId + " not found in data file");
}

// Save a single patient (add or update)
function savePatient(PatientRecord patient) returns error? {
    PatientData data = check loadPatientData();
    
    // Check if patient exists and update, otherwise add
    boolean found = false;
    foreach int i in 0..<data.patients.length() {
        if (data.patients[i].demographics.patientId == patient.demographics.patientId) {
            data.patients[i] = patient;
            found = true;
            break;
        }
    }
    
    if (!found) {
        data.patients.push(patient);
    }
    
    check savePatientData(data = data);
}

// Find latest lab result by name
function findLatestLab(LabResult[] labs, string labName) returns LabResult? {
    LabResult? latestLab = ();
    
    foreach LabResult lab in labs {
        if (lab.name.toLowerAscii() == labName.toLowerAscii()) {
            if (latestLab is () || lab.recordDate > latestLab.recordDate) {
                latestLab = lab;
            }
        }
    }
    
    return latestLab;
}

// Create basic patient record for new patients
function createBasicPatient(string patientId) returns PatientRecord {
    Demographics demographics = {
        patientId: patientId,
        firstName: "Unknown",
        lastName: "Patient",
        dateOfBirth: "1900-01-01",
        gender: "Unknown"
    };
    
    return {
        demographics: demographics,
        problems: [],
        medications: [],
        vitals: [],
        labs: []
    };
}

// Get sample patients for initialization
function getSamplePatients() returns PatientRecord[] {
    PatientRecord patient1 = {
        demographics: {
            patientId: "12873",
            firstName: "John",
            lastName: "Doe",
            dateOfBirth: "1980-05-15",
            gender: "Male",
            address: "123 Main St, Anytown, ST 12345",
            phone: "(555) 123-4567",
            email: "john.doe@email.com"
        },
        problems: [
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
        ],
        medications: [
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
        ],
        vitals: [
            {
                recordDate: "2024-01-15",
                bloodPressureSystolic: 135.0,
                bloodPressureDiastolic: 85.0,
                heartRate: 72.0,
                temperature: 98.6,
                weight: 180.5,
                height: 70.0
            }
        ],
        labs: [
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
            },
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
            }
        ]
    };

    PatientRecord patient2 = {
        demographics: {
            patientId: "12874",
            firstName: "Jane",
            lastName: "Smith",
            dateOfBirth: "1975-08-22",
            gender: "Female",
            address: "456 Oak Ave, Somewhere, ST 67890",
            phone: "(555) 987-6543",
            email: "jane.smith@email.com"
        },
        problems: [
            {
                problemId: "P003",
                description: "Chronic Kidney Disease",
                status: "active",
                onsetDate: "2021-06-10",
                severity: "moderate"
            }
        ],
        medications: [
            {
                medicationId: "M003",
                name: "Losartan",
                dosage: "25mg",
                frequency: "once daily",
                prescribedDate: "2021-06-10",
                status: "active"
            }
        ],
        vitals: [
            {
                recordDate: "2024-01-12",
                bloodPressureSystolic: 128.0,
                bloodPressureDiastolic: 78.0,
                heartRate: 68.0,
                temperature: 98.4,
                weight: 145.2,
                height: 65.0
            }
        ],
        labs: [
            {
                labId: "L007",
                name: "eGFR",
                value: 45.0,
                unit: "mL/min/1.73m²",
                referenceRange: ">60",
                recordDate: "2024-01-08",
                status: "abnormal"
            },
            {
                labId: "L008",
                name: "A1c",
                value: 5.8,
                unit: "%",
                referenceRange: "<7.0",
                recordDate: "2024-01-08",
                status: "normal"
            }
        ]
    };

    PatientRecord patient3 = {
        demographics: {
            patientId: "12875",
            firstName: "Bob",
            lastName: "Johnson",
            dateOfBirth: "1965-12-03",
            gender: "Male",
            address: "789 Pine St, Elsewhere, ST 54321",
            phone: "(555) 456-7890",
            email: "bob.johnson@email.com"
        },
        problems: [
            {
                problemId: "P004",
                description: "Type 1 Diabetes Mellitus",
                status: "active",
                onsetDate: "1985-03-20",
                severity: "severe"
            }
        ],
        medications: [
            {
                medicationId: "M004",
                name: "Insulin",
                dosage: "20 units",
                frequency: "twice daily",
                prescribedDate: "1985-03-20",
                status: "active"
            }
        ],
        vitals: [
            {
                recordDate: "2024-01-10",
                bloodPressureSystolic: 140.0,
                bloodPressureDiastolic: 90.0,
                heartRate: 75.0,
                temperature: 98.8,
                weight: 175.0,
                height: 72.0
            }
        ],
        labs: [
            {
                labId: "L009",
                name: "A1c",
                value: 8.5,
                unit: "%",
                referenceRange: "<7.0",
                recordDate: "2024-01-05",
                status: "abnormal"
            },
            {
                labId: "L010",
                name: "eGFR",
                value: 75.0,
                unit: "mL/min/1.73m²",
                referenceRange: ">60",
                recordDate: "2024-01-05",
                status: "normal"
            }
        ]
    };

    return [patient1, patient2, patient3];
}

// Helper function to generate timestamp for order ID
function generateTimestamp() returns string {
    return "20240115123045";
}

// Initialize the data file when the module loads
function init() {
    initializeDataFile();
}
