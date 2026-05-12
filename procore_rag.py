import os
import json
import requests

PROCORE_BASE_URL = "https://sandbox.procore.com"
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "procore_token.json")
TOKEN_URL = "https://login-sandbox.procore.com/oauth/token"

def refresh_access_token(refresh_token, client_id, client_secret):
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    })
    if resp.status_code == 200:
        return resp.json().get("access_token")
    return None

def get_procore_token():
    try:
        import streamlit as st
        client_id = st.secrets.get("PROCORE_CLIENT_ID")
        client_secret = st.secrets.get("PROCORE_CLIENT_SECRET")
        refresh_token = st.secrets.get("PROCORE_REFRESH_TOKEN")
        if client_id and client_secret and refresh_token:
            return refresh_access_token(refresh_token, client_id, client_secret)
    except Exception:
        pass
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
        return data.get("access_token")
    return None

def get_companies(token):
    headers = {"Authorization": "Bearer " + token}
    response = requests.get(
        PROCORE_BASE_URL + "/rest/v1.0/companies",
        headers=headers
    )
    if response.status_code == 200:
        return response.json()
    return []

def get_projects(token, company_id):
    headers = {"Authorization": "Bearer " + token}
    response = requests.get(
        PROCORE_BASE_URL + "/rest/v1.0/projects?company_id=" + str(company_id),
        headers=headers
    )
    if response.status_code == 200:
        return response.json()
    return []

def get_rfis(token, project_id, company_id):
    headers = {"Authorization": "Bearer " + token}
    response = requests.get(
        PROCORE_BASE_URL + "/rest/v1.0/projects/" + str(project_id) + "/rfis?company_id=" + str(company_id),
        headers=headers
    )
    if response.status_code == 200:
        return response.json()
    return []

def get_submittals(token, project_id, company_id):
    headers = {"Authorization": "Bearer " + token}
    response = requests.get(
        PROCORE_BASE_URL + "/rest/v1.0/projects/" + str(project_id) + "/submittals?company_id=" + str(company_id),
        headers=headers
    )
    if response.status_code == 200:
        return response.json()
    return []

def format_procore_context(projects, rfis, submittals):
    context = "\n\n=== PROCORE DATA ===\n"
    if projects:
        context += "\nProjects:\n"
        for p in projects[:5]:
            context += "- " + p.get("name", "") + " (ID: " + str(p.get("id", "")) + ")\n"
    if rfis:
        context += "\nRFIs:\n"
        for rfi in rfis[:20]:
            context += "- RFI #" + str(rfi.get("number", "")) + ": " + str(rfi.get("subject", "")) + " | Status: " + str(rfi.get("status", "")) + "\n"
    if submittals:
        context += "\nSubmittals:\n"
        for sub in submittals[:20]:
            context += "- #" + str(sub.get("number", "")) + ": " + str(sub.get("title", "")) + " | Status: " + str(sub.get("status", "")) + "\n"
    return context

def fetch_procore_context(question):
    token = get_procore_token()
    if not token:
        return ""
    companies = get_companies(token)
    if not companies:
        return ""
    company_id = companies[0].get("id")
    projects = get_projects(token, company_id)
    if not projects:
        return ""
    project_id = projects[0].get("id")
    rfis = get_rfis(token, project_id, company_id)
    submittals = get_submittals(token, project_id, company_id)
    return format_procore_context(projects, rfis, submittals)
