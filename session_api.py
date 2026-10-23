"""Isolated API process for Step 4C.3; does NOT issue authentication sessions yet.

Do not treat this as a completed authentication implementation.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

@app.get('/api/session/health')
def health():
    return {'status': 'ok', 'component': 'session-api'}

@app.api_route('/api/session/{path:path}', methods=['GET','POST','PUT','PATCH','DELETE'])
def unavailable(path: str):
    return JSONResponse(status_code=501, content={'error': 'Session persistence is not enabled'})
