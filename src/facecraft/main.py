"""
Facecraft - AI Portrait Processing API

Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from facecraft import __version__
from facecraft.core.config import settings
from facecraft.api.routes import health_router, process_router
from facecraft.api.dependencies import init_processor, cleanup_old_files


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print("=" * 60)
    print("Facecraft - AI Portrait Processing API")
    print(f"Version: {__version__}")
    print("=" * 60)

    # Initialize processor (loads models)
    try:
        processor = init_processor()
        print(f"Device: {settings.get_device()}")
        print(f"Face alignment: {'enabled' if processor.has_face_alignment else 'disabled'}")
        print(f"Face enhancement: {'enabled' if processor.has_face_enhancement else 'disabled'}")
        print("Models loaded successfully")
    except Exception as e:
        print(f"Warning: Error initializing processor: {e}")

    # Cleanup old files
    cleanup_old_files(settings.cleanup_age_hours)
    print("Old files cleaned up")

    print("=" * 60)
    print("Server ready for requests!")
    print("=" * 60)

    yield

    # Shutdown
    print("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Facecraft API",
    description="""
## AI Portrait Processing API

Professional portrait/headshot processing with AI-powered:
- **Background removal** using u2net_human_seg model
- **Face detection** and alignment using dlib
- **Face quality enhancement** using CodeFormer
- **Photo enhancement** (exposure, white balance, sharpening)
- **Oval mask** with feathered edges

### Quick Start

Upload an image to `/api/v1/process` to get a professionally processed portrait.

### Output Formats

- **PNG** with transparent background (when oval mask enabled)
- **JPEG** with solid background (max 99KB for AD compatibility)
    """,
    version=__version__,
    docs_url="/docs",
    redoc_url=None,  # Disabled as per user request
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(process_router)


# Root endpoint redirects to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirect to API documentation."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "facecraft.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers
    )
