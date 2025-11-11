# Granting Firestore Permissions to Cloud Run Service Account

To resolve the 'PermissionDenied' error, you need to grant the Cloud Run service account the necessary permissions to access Firestore. Please follow these steps:

## 1. Identify the Service Account

1.  Go to the Google Cloud Console: [https://console.cloud.google.com/](https://console.cloud.google.com/)
2.  Navigate to **Cloud Run** and select your `empathy-hub-backend` service.
3.  In the service details, find the **Service account** associated with your Cloud Run revision. It typically looks like `[PROJECT_NUMBER]-compute@developer.gserviceaccount.com`. Make a note of this email address.

## 2. Grant Permissions

1.  Go to **IAM & Admin** -> **IAM** in the Google Cloud Console.
2.  Click on **+ GRANT ACCESS**.
3.  In the **New principals** field, paste the service account email you identified in step 1.
4.  In the **Select a role** field, search for and select **Cloud Datastore User** (or **Cloud Datastore Editor** if you need broader write access).
5.  Click **SAVE**.

## 3. Redeploy the Backend

After granting the permissions, you will need to redeploy the backend for the changes to take effect. Since you've already made the `PostCreate` schema change locally, pushing your current changes to the `main` branch will trigger a new deployment with the updated code and (hopefully) the correct permissions.