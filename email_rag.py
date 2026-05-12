import os
import json
import msal
import requests

TOKEN_CACHE_FILE = "/tmp/fieldbook_token_cache.json"

def get_graph_token_device_flow():
    client_id = os.getenv('AZURE_AD_CLIENT_ID')
    
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        cache.deserialize(open(TOKEN_CACHE_FILE).read())
    
    app = msal.PublicClientApplication(
        client_id,
        authority="https://login.microsoftonline.com/consumers",
        token_cache=cache
    )
    
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(
            scopes=["https://graph.microsoft.com/Mail.Read"],
            account=accounts[0]
        )
        if result and "access_token" in result:
            open(TOKEN_CACHE_FILE, "w").write(cache.serialize())
            return result["access_token"]
    
    flow = app.initiate_device_flow(scopes=["https://graph.microsoft.com/Mail.Read"])
    if "message" not in flow:
        print("Error starting device flow:", flow)
        return None
    
    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    
    if "access_token" in result:
        open(TOKEN_CACHE_FILE, "w").write(cache.serialize())
        return result["access_token"]
    return None

def fetch_emails(user_email=None, max_emails=50):
    token = get_graph_token_device_flow()
    if not token:
        print("Could not get token")
        return []
    headers = {"Authorization": f"Bearer {token}"}
    url = "https://graph.microsoft.com/v1.0/me/messages"
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
