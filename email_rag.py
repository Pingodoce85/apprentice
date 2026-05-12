import os
import msal
import requests

def get_graph_token():
    tenant_id = os.getenv('AZURE_AD_TENANT_ID')
    client_id = os.getenv('AZURE_AD_CLIENT_ID')
    client_secret = os.getenv('AZURE_AD_CLIENT_SECRET')
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result.get("access_token")

def fetch_emails(user_email, max_emails=50):
    token = get_graph_token()
    if not token:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages"
    params = {
        "$top": max_emails,
        "$select": "subject,from,receivedDateTime,body,hasAttachments",
        "$orderby": "receivedDateTime desc"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print("Graph API error:", response.text)
        return []
    messages = response.json().get("value", [])
    emails = []
    for msg in messages:
        emails.append({
            "subject": msg.get("subject", "No Subject"),
            "from": msg.get("from", {}).get("emailAddress", {}).get("address", "Unknown"),
            "date": msg.get("receivedDateTime", ""),
            "body": msg.get("body", {}).get("content", ""),
            "has_attachments": msg.get("hasAttachments", False)
        })
    return emails

def format_emails_for_context(emails):
    context = ""
    for email in emails:
        context += "\n---EMAIL---\n"
        context += "From: " + email["from"] + "\n"
        context += "Date: " + email["date"] + "\n"
        context += "Subject: " + email["subject"] + "\n"
        context += "Body: " + email["body"][:2000] + "\n"
    return context
