from fastapi import FastAPI

from app.routers.audits import router as audits_router

app = FastAPI(title="SEO Auditor", version="0.1.0")

app.include_router(audits_router, prefix="/audits", tags=["audits"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}