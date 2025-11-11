#!/bin/bash
PROJECT_ID="anonymous-hubs-477707"
SERVICE_NAME="empathy-hub-backend" # Assumed service name, verify in Google Cloud Console if logs are not found
REGION="us-central1" # Assuming us-central1 based on the URL
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME} AND resource.labels.location=${REGION} AND timestamp>=\"$(date -d '1 hour ago' --iso-8601=seconds)\"" --project=${PROJECT_ID} --limit=100 --format=json | tee /home/s1d/Projects/Empathy_Hub/empathy-hub-backend/logs/google-cloud/backend_logs_$(date +%Y%m%d_%H%M%S).json
