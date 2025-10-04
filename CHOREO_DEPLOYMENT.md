# Deploying to WSO2 Choreo Cloud

This guide explains how to deploy the EHR Backend and Trial Registry Backend services as Python components in WSO2 Choreo.

## Overview

Both services are FastAPI-based Python applications that can be deployed as Service components in Choreo:

- **EHR Backend**: Provides patient data, lab results, and medication information
- **Trial Registry Backend**: Manages clinical trial data

## Prerequisites

1. WSO2 Choreo account (sign up at https://console.choreo.dev/)
2. Git repository with this codebase
3. GitHub organization access (if using GitHub integration)

## Component Configuration

Each backend has a `.choreo/component.yaml` file that defines:
- Component type: `Service`
- Inbound endpoints (REST API)
- Port configuration
- Python base image
- Environment variables

### EHR Backend
- **Port**: 8001
- **Config**: `ehr-backend/.choreo/component.yaml`
- **Entry Point**: `uvicorn app:app`

### Trial Registry Backend
- **Port**: 8002
- **Config**: `trial-registry-backend/.choreo/component.yaml`
- **Entry Point**: `uvicorn app:app`

## Deployment Steps

### 1. Create Component in Choreo

For each backend service:

1. **Log in to Choreo Console**: https://console.choreo.dev/
2. **Create a New Component**:
   - Click "Create" → "Component"
   - Select "Service" as component type
   - Choose "Python" as the buildpack

3. **Connect Repository**:
   - Connect your GitHub/GitLab repository
   - Select the branch (e.g., `main`)
   - Set the project path:
     - For EHR Backend: `/ehr-backend`
     - For Trial Registry Backend: `/trial-registry-backend`

4. **Configure Component**:
   - Choreo will automatically detect the `.choreo/component.yaml` file
   - Review the configuration
   - Click "Create"

### 2. Build Configuration

Choreo will use:
- **Base Image**: `python:3.11`
- **Build Type**: `buildpacks` (automatic detection)
- **Dependencies**: Installed from `requirements.txt`
- **Process**: Defined in `Procfile`

The `Procfile` tells Choreo how to start the service:
```
web: uvicorn app:app --host 0.0.0.0 --port <PORT>
```

### 3. Environment Variables

Configure environment variables in Choreo Console:

#### EHR Backend
```yaml
EHR_SERVICE_TITLE: "EHR Service"
EHR_SERVICE_DESCRIPTION: "Demo API offering patient summaries"
EHR_ALLOW_ORIGINS: "*"  # Update for production
```

#### Trial Registry Backend
```yaml
TRIAL_REGISTRY_TITLE: "Clinical Research Services API"
TRIAL_REGISTRY_DESCRIPTION: "REST API for managing clinical trials"
TRIAL_REGISTRY_ALLOW_ORIGINS: "*"  # Update for production
```

### 4. Deploy

1. **Build**: Choreo will build your component automatically
2. **Deploy to Development**: Click "Deploy" for the development environment
3. **Promote**: Once tested, promote to staging/production

### 5. Access Your Services

After deployment, Choreo provides:
- **Service URL**: e.g., `https://<org>-<component>.choreoapis.dev`
- **API Documentation**: Swagger UI available at `/docs`
- **Health Check**: `/health` endpoint

## Testing Deployed Services

### Test EHR Backend
```bash
# Get patient summary
curl https://<your-ehr-service-url>/patients/12873/summary

# Get lab results
curl https://<your-ehr-service-url>/patients/12873/labs
```

### Test Trial Registry Backend
```bash
# List trials
curl https://<your-trial-registry-url>/trials

# Get specific trial
curl https://<your-trial-registry-url>/trials/1
```

## Updating Services

When you push changes to your repository:
1. Choreo automatically detects the changes
2. Creates a new build
3. Deploy the new version to your environments

## Connecting to Agents

After deploying, update the agent configuration:

### In `care-plan-agent/.env`:
```bash
EHR_SERVICE_URL=https://<your-ehr-service-url>
```

### In `evidence-agent/.env`:
```bash
TRIAL_REGISTRY_URL=https://<your-trial-registry-url>
```

## Production Considerations

1. **CORS Configuration**: Update `ALLOW_ORIGINS` to specific domains instead of `*`
2. **Authentication**: Add API key or OAuth2 authentication if needed
3. **Rate Limiting**: Configure rate limits in Choreo
4. **Monitoring**: Use Choreo's built-in observability features
5. **Scaling**: Configure auto-scaling based on traffic patterns

## File Structure

```
ehr-backend/
├── .choreo/
│   └── component.yaml          # Choreo component configuration
├── Procfile                    # Process definition for Choreo
├── app.py                      # FastAPI application
├── requirements.txt            # Python dependencies
└── .env.example               # Environment variable template

trial-registry-backend/
├── .choreo/
│   └── component.yaml          # Choreo component configuration
├── Procfile                    # Process definition for Choreo
├── app.py                      # FastAPI application
├── requirements.txt            # Python dependencies
└── .env.example               # Environment variable template
```

## Troubleshooting

### Build Fails
- Check that `requirements.txt` has all dependencies
- Verify Python version compatibility (3.11)
- Review build logs in Choreo Console

### Service Not Starting
- Check `Procfile` syntax
- Verify port configuration matches `component.yaml`
- Review runtime logs in Choreo Console

### API Not Accessible
- Verify endpoint configuration in `component.yaml`
- Check network visibility settings
- Ensure CORS is configured correctly

## Support

- Choreo Documentation: https://wso2.com/choreo/docs/
- Choreo Community: https://discord.gg/wso2
- GitHub Issues: Create an issue in your repository

## Next Steps

1. Deploy both backend services to Choreo
2. Note the deployed URLs
3. Update agent configurations with the new URLs
4. Deploy the agents (care-plan-agent and evidence-agent) as separate components
5. Configure API Manager to route traffic to your deployed services
