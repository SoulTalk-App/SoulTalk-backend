from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.api.auth import router as auth_router


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Keycloak Server: {settings.KEYCLOAK_SERVER_URL}")
    logger.info(f"Keycloak Realm: {settings.KEYCLOAK_REALM}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="SoulTalk Backend API with Keycloak Authentication",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted Host Middleware (for production)
if settings.ENVIRONMENT == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*.soultalk.com"])

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "healthy"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/api/protected")
async def protected_route():
    """Example protected route (requires authentication)"""
    from app.api.auth import get_current_user
    from fastapi import Depends
    
    async def protected_endpoint(current_user: dict = Depends(get_current_user)):
        return {
            "message": "This is a protected route",
            "user": {
                "id": current_user.get("sub"),
                "email": current_user.get("email"),
                "name": current_user.get("name")
            }
        }
    
    return await protected_endpoint()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )