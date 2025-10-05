// Trial data structure matching the Python model
public type Trial record {
    int id;
    string? nctId?;
    string title;
    string condition;
    string phase;
    string status;
    string principalInvestigator;
    string startDate; // Using string for date representation
    string? endDate?;
    decimal? siteDistanceKm?;
    string? eligibilitySummary?;
};

// Service information structure
public type ServiceInfo record {
    string name;
    string description;
    string[] capabilities;
};

// Response structure for Evidence Agent
public type TrialMetadata record {
    string nctId;
    decimal distance;
    string eligibilitySummary;
    int id;
    string title;
    string condition;
    string phase;
    string status;
};

// API Response structures
public type TrialsResponse record {
    TrialMetadata[] trials;
    int totalCount;
};

public type PostTrialResponse record {
    string message;
    int trialsAdded;
};
