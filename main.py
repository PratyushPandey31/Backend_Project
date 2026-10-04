import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import seed_database_if_empty
from app.api.routes import router as api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure SQLite tables and seed data exist
    seed_database_if_empty()
    yield

app = FastAPI(
    title="AI Real Estate Portfolio Analyst",
    description="Conversational wealth analyst for real estate portfolios with simulated WhatsApp and Business Observation UI.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets
static_dir = os.path.join(os.path.dirname(__file__), "app", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount API routes
app.include_router(api_router, prefix="/api")

# WhatsApp Client Chat Interface
@app.get("/")
async def serve_whatsapp_ui():
    return FileResponse(os.path.join(static_dir, "index.html"))

# Business Observation & Control Interface
@app.get("/business")
async def serve_business_ui():
    return FileResponse(os.path.join(static_dir, "business.html"))

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
