# ============================================================
#  Backend container ki recipe (Python FastAPI app)
# ============================================================

# 1) Base: ek chhota Python 3.12 image (slim = halka)
FROM python:3.12-slim

# 2) Container ke andar kaam karne ki jagah
WORKDIR /app

# 3) Pehle sirf requirements copy karo + install karo
#    (alag step isliye taaki code badalne par bhi libraries dobara install na hon — fast builds)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4) Ab baaki saara backend code copy karo
COPY . .

# 5) RAG index build time par hi bana do: embedding model download + standards
#    ingest image mein bake ho jaate hain. Startup par ensure_ingested() hash
#    match dekh kar skip kar deta hai — pehla request slow nahi hota.
RUN python -c "import rag; rag.ensure_ingested()"

# 6) Ye container port 8000 par sunega
EXPOSE 8000

# 7) Container start hone par ye command chalegi
#    host 0.0.0.0 = bahar se accessible. PORT cloud (Render) deta hai;
#    local/compose par PORT set nahi hota to 8000 use hoga.
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
