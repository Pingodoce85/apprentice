import os
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

def extract_with_document_intelligence(pdf_bytes):
    endpoint = os.getenv('AZURE_DOC_INTELLIGENCE_ENDPOINT') or ''
    key = os.getenv('AZURE_DOC_INTELLIGENCE_KEY') or ''
    
    if not endpoint or not key:
        return None
    
    try:
        client = DocumentAnalysisClient(
            endpoint=endpoint.strip(),
            credential=AzureKeyCredential(key.strip())
        )
        poller = client.begin_analyze_document('prebuilt-read', pdf_bytes)
        result = poller.result()
        
        text = ''
        for page in result.pages:
            text += '\n[Page ' + str(page.page_number) + ']\n'
            for line in page.lines:
                text += line.content + '\n'
        
        return text if text.strip() else None
    except Exception as e:
        print('Document Intelligence error:', e)
        return None
