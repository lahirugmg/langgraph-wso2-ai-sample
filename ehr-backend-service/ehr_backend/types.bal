// Patient demographic information
public type Demographics record {
    string patientId;
    string firstName;
    string lastName;
    string dateOfBirth;
    string gender;
    string address?;
    string phone?;
    string email?;
};

// Medical problem/condition
public type Problem record {
    string problemId;
    string description;
    string status; // active, resolved, etc.
    string onsetDate?;
    string severity?;
};

// Medication information
public type Medication record {
    string medicationId;
    string name;
    string dosage;
    string frequency;
    string prescribedDate;
    string status; // active, discontinued, etc.
};

// Vital signs
public type Vitals record {
    string recordDate;
    decimal? bloodPressureSystolic;
    decimal? bloodPressureDiastolic;
    decimal? heartRate;
    decimal? temperature;
    decimal? weight;
    decimal? height;
};

// Lab result
public type LabResult record {
    string labId;
    string name;
    decimal value;
    string unit;
    string referenceRange;
    string recordDate;
    string status; // normal, abnormal, critical
};

// Patient summary response
public type PatientSummary record {
    Demographics demographics;
    Problem[] problems;
    Medication[] medications;
    Vitals[] vitals;
    LabResult? lastA1c;
    LabResult? lastEgfr;
};

// Labs response
public type LabsResponse record {
    string patientId;
    LabResult[] labs;
};

// Medication order request
public type MedicationOrder record {
    string patientId;
    string medicationName;
    string dosage;
    string frequency;
    string duration;
    string prescriberId;
    string notes?;
};

// Order response
public type OrderResponse record {
    string orderId;
    string status;
    string message;
};

// Error response
public type ErrorResponse record {
    string 'error;
    string message;
};

// Complete patient record for file storage
public type PatientRecord record {
    Demographics demographics;
    Problem[] problems;
    Medication[] medications;
    Vitals[] vitals;
    LabResult[] labs;
};

// Data container for the entire data file
public type PatientData record {
    PatientRecord[] patients;
};
