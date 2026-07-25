$content = @'
# Serveur web
fastapi>=0.110.0
uvicorn>=0.29.0
pydantic>=2.0.0

# Pipeline RAG
chromadb>=0.5.0
fastembed>=0.3.0

# Lecture des documents
pdfplumber>=0.11.0
pypdf>=4.0.0

# Modèles de langage
anthropic>=0.34.0
openai>=1.30.0

# Utilitaires
python-dotenv>=1.0.0

# Interface Streamlit (optionnelle en production, utile en local)
streamlit>=1.36.0
'@
[System.IO.File]::WriteAllText((Join-Path $PWD 'requirements.txt'), $content, (New-Object System.Text.UTF8Encoding $false))
$content = @'
# render.yaml — recette de déploiement pour Render.
# À placer à la racine du dépôt. Render le lit automatiquement.

services:
  - type: web
    name: assistant-demo
    runtime: python
    plan: free                 # gratuit pour tester ; passer à "starter" (~7$/mois) pour un client
    region: frankfurt          # Europe ; "oregon" pour l'Amérique du Nord
    buildCommand: pip install -r requirements.txt && python ingest.py
    startCommand: uvicorn server:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: LLM_PROVIDER
        value: anthropic
      - key: ANTHROPIC_MODEL
        value: claude-haiku-4-5
      - key: ANTHROPIC_API_KEY
        sync: false            # à saisir à la main dans Render, jamais dans le code
      - key: DATA_DIR
        value: data
      - key: PYTHON_VERSION
        value: "3.12"
'@
[System.IO.File]::WriteAllText((Join-Path $PWD 'render.yaml'), $content, (New-Object System.Text.UTF8Encoding $false))
Write-Host 'Fichiers recrees en UTF-8 sans BOM.'