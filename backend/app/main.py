from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.analyze import router as analyze_router
from app.api.live import router as live_router
from app.database.connection import engine, Base
import app.database.models  # Import to register models in Base metadata

def create_app() -> FastAPI:
    """
    App Factory function to initialize and configure the FastAPI application.
    """
    # Initialize SQLite Database tables on startup
    Base.metadata.create_all(bind=engine)

    app = FastAPI(
        title="AI Scam Detection API",
        description="Backend service for detecting synthetic voices, classifying scams, and retrieving RBI advisories using RAG.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # 1. Configure CORS
    # React default Vite port is 5173. We allow localhost for development.
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Register API Routers
    app.include_router(analyze_router, prefix="/api/v1")
    app.include_router(live_router, prefix="/api/v1")

    # 3. Root Endpoint for Health Check
    @app.get("/")
    async def root():
        return {
            "status": "healthy",
            "message": "AI Scam Detection Backend is active.",
            "version": "1.0.0"
        }

    return app

app = create_app()
