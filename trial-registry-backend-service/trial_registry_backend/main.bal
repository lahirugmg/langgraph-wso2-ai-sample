import ballerina/http;
import ballerina/io;

// HTTP listener on port 8002
listener http:Listener httpListener = new (8002);

// Initialize data on startup
function init() {
    error? initResult = initializeDataFile();
    if initResult is error {
        // Log error but continue service startup
    }
}

// Services endpoint
service /services on httpListener {
    // GET /services - Get service capabilities
    resource function get .() returns ServiceInfo {
        ServiceInfo serviceInfo = {
            name: "Clinical Research Services API",
            description: "REST API for managing clinical trials used by the evidence and care-plan agents",
            capabilities: [
                "List all clinical trials",
                "Create new clinical trials", 
                "Retrieve individual trial details",
                "Service metadata"
            ]
        };
        return serviceInfo;
    }
}

// Trial Registry Service
service /trials on httpListener {
    
    // GET /trials - Retrieve all trials with metadata
    resource function get .() returns TrialsResponse|http:InternalServerError {
        Trial[]|error trialsResult = readTrialsFromFile();
        
        if trialsResult is error {
            return http:INTERNAL_SERVER_ERROR;
        }
        
        Trial[] trials = trialsResult;
        TrialMetadata[] trialMetadata = [];
        
        foreach Trial trial in trials {
            string nctIdValue = trial?.nctId ?: "NCT" + trial.id.toString();
            decimal distanceValue = trial?.siteDistanceKm ?: 0.0;
            string eligibilityValue = trial?.eligibilitySummary ?: "Standard eligibility criteria apply";
            
            TrialMetadata metadata = {
                nctId: nctIdValue,
                distance: distanceValue,
                eligibilitySummary: eligibilityValue,
                id: trial.id,
                title: trial.title,
                condition: trial.condition,
                phase: trial.phase,
                status: trial.status
            };
            trialMetadata.push(metadata);
        }
        
        TrialsResponse response = {
            trials: trialMetadata,
            totalCount: trialMetadata.length()
        };
        
        return response;
    }
    
    // GET /trials/{trial_id} - Retrieve a specific trial
    resource function get [int trialId]() returns Trial|http:NotFound|http:InternalServerError {
        Trial[]|error trialsResult = readTrialsFromFile();
        
        if trialsResult is error {
            return http:INTERNAL_SERVER_ERROR;
        }
        
        Trial[] trials = trialsResult;
        
        foreach Trial trial in trials {
            if trial.id == trialId {
                return trial;
            }
        }
        
        http:NotFound notFound = {
            body: string `Trial with ID ${trialId} not found`
        };
        return notFound;
    }
    
    // POST /trials - Add new trials
    resource function post .(Trial[] newTrials) returns PostTrialResponse|http:BadRequest|http:InternalServerError {
        if newTrials.length() == 0 {
            http:BadRequest badRequest = {
                body: "No trials provided"
            };
            return badRequest;
        }
        
        Trial[]|error existingTrialsResult = readTrialsFromFile();
        Trial[] existingTrials = [];
        
        if existingTrialsResult is Trial[] {
            existingTrials = existingTrialsResult;
        }
        
        // Add new trials to existing ones
        foreach Trial newTrial in newTrials {
            existingTrials.push(newTrial);
        }
        
        error? writeResult = writeTrialsToFile(existingTrials);
        
        if writeResult is error {
            return http:INTERNAL_SERVER_ERROR;
        }
        
        PostTrialResponse response = {
            message: "Trials added successfully",
            trialsAdded: newTrials.length()
        };
        
        return response;
    }
}

// Function to initialize data.txt with sample data
function initializeDataFile() returns error? {
    // Check if data.txt already exists
    json|io:Error existingContent = io:fileReadJson(path = "data.txt");
    
    if existingContent is json {
        // File exists, don't overwrite
        return;
    }
    
    // Create initial sample data
    Trial[] sampleTrials = [
        {
            id: 1,
            nctId: "NCT05566789",
            title: "SGLT2i Outcomes in CKD Stage 3",
            condition: "Type 2 diabetes mellitus",
            phase: "Phase III",
            status: "Recruiting",
            principalInvestigator: "Dr. Amina Perera",
            startDate: "2023-09-01",
            endDate: (),
            siteDistanceKm: 12.4,
            eligibilitySummary: "Adults 40-75 with type 2 diabetes and eGFR 45-60"
        },
        {
            id: 2,
            nctId: "NCT07654321",
            title: "GLP-1 RA Renal Outcomes Registry",
            condition: "Type 2 diabetes mellitus",
            phase: "Phase II",
            status: "Recruiting",
            principalInvestigator: "Dr. Liam Chen",
            startDate: "2024-02-12",
            endDate: "2025-05-30",
            siteDistanceKm: 14.9,
            eligibilitySummary: "T2D adults with eGFR 30-60 on stable metformin"
        },
        {
            id: 3,
            nctId: "NCT09999888",
            title: "CardioHealth Outcomes Study",
            condition: "Hypertension",
            phase: "Phase III",
            status: "Completed",
            principalInvestigator: "Dr. Amina Perera",
            startDate: "2021-05-01",
            endDate: "2023-03-10",
            siteDistanceKm: 52.0,
            eligibilitySummary: "Adults with resistant hypertension"
        }
    ];
    
    error? writeResult = writeTrialsToFile(sampleTrials);
    return writeResult;
}

// Function to read trials from data.txt
function readTrialsFromFile() returns Trial[]|error {
    json|io:Error fileContent = io:fileReadJson(path = "data.txt");
    
    if fileContent is io:Error {
        // If file doesn't exist, return empty array
        return [];
    }
    
    Trial[]|error trials = fileContent.cloneWithType();
    return trials;
}

// Function to write trials to data.txt
function writeTrialsToFile(Trial[] trials) returns error? {
    json trialsJson = trials.toJson();
    io:Error? writeResult = io:fileWriteJson(path = "data.txt", content = trialsJson);
    return writeResult;
}
