"""Image processing endpoints."""

import time
import uuid
import shutil
import base64
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Depends
from fastapi.responses import FileResponse

from facecraft.api.schemas.requests import ProcessingOptionsRequest
from facecraft.api.schemas.responses import (
    ProcessResponse,
    ProcessResult,
    FacePosition,
    BatchResponse,
    BatchResultItem,
)
from facecraft.api.dependencies import get_processor, get_upload_dir, get_output_dir
from facecraft.processing.processor import PhotoProcessor
from facecraft.core.config import settings

router = APIRouter(prefix="/api/v1", tags=["processing"])


@router.post("/process", response_model=ProcessResponse)
async def process_single_photo(
    file: UploadFile = File(...),
    width: int = Form(default=648),
    height: int = Form(default=648),
    background_r: int = Form(default=240),
    background_g: int = Form(default=240),
    background_b: int = Form(default=240),
    face_margin: float = Form(default=0.3),
    use_oval_mask: bool = Form(default=True),
    enhance_face: bool = Form(default=True),
    enhance_fidelity: float = Form(default=0.7),
    return_base64: bool = Form(default=False),
    processor: PhotoProcessor = Depends(get_processor),
    upload_dir: Path = Depends(get_upload_dir),
    output_dir: Path = Depends(get_output_dir),
):
    """
    Process a single photo.

    Upload an image and receive a processed portrait with:
    - Background removed
    - Face detected and centered
    - Quality enhanced
    - Optional oval mask applied

    **Parameters:**
    - **file**: Image to process (JPG, PNG, etc.)
    - **width/height**: Output dimensions (default: 648x648)
    - **background_r/g/b**: Background color RGB values
    - **face_margin**: Margin around face (0.0-1.0)
    - **use_oval_mask**: Apply oval mask with transparency
    - **enhance_face**: Use AI face enhancement
    - **enhance_fidelity**: Face enhancement fidelity (0.0-1.0)
    - **return_base64**: Return images as base64 in response

    **Returns:**
    - Job ID for downloading results
    - Processing statistics
    - Download URLs for PNG and JPG versions
    """
    start_time = time.time()
    job_id = str(uuid.uuid4())[:8]

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format. Allowed: {', '.join(allowed_extensions)}"
        )

    # Save uploaded file
    upload_path = upload_dir / f"{job_id}_{file.filename}"
    try:
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Prepare output paths
    job_output_dir = output_dir / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)
    output_path = job_output_dir / f"{Path(file.filename).stem}.png"

    # Create processing options
    from facecraft.processing.processor import ProcessingOptions
    options = ProcessingOptions(
        width=width,
        height=height,
        background_color=(background_r, background_g, background_b),
        face_margin=face_margin,
        use_oval_mask=use_oval_mask,
        enhance_face=enhance_face,
        enhance_fidelity=enhance_fidelity,
        enhance_photo=True,
        max_jpeg_size_kb=99
    )

    # Process image
    try:
        result = processor.process_image(str(upload_path), str(output_path), options)
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    # Cleanup upload
    upload_path.unlink(missing_ok=True)

    # Calculate processing time
    processing_time = int((time.time() - start_time) * 1000)

    if not result.success:
        error_messages = {
            "no_face_detected": "No face could be detected in the image"
        }
        return ProcessResponse(
            success=False,
            job_id=job_id,
            processing_time_ms=processing_time,
            error=result.error,
            error_message=error_messages.get(result.error, result.error)
        )

    # Build response
    response = ProcessResponse(
        success=True,
        job_id=job_id,
        processing_time_ms=processing_time,
        result=ProcessResult(
            face_detected=result.face_detected,
            face_count=result.face_count,
            face_position=FacePosition(**result.face_position) if result.face_position else None,
            output_size={"width": width, "height": height},
            file_size_bytes=result.file_size_bytes
        ),
        png_url=f"/api/v1/download/{job_id}/png" if result.png_path else None,
        jpg_url=f"/api/v1/download/{job_id}/jpg" if result.jpg_path else None
    )

    # Add base64 if requested
    if return_base64:
        if result.png_path and Path(result.png_path).exists():
            with open(result.png_path, "rb") as f:
                response.png_base64 = base64.b64encode(f.read()).decode()
        if result.jpg_path and Path(result.jpg_path).exists():
            with open(result.jpg_path, "rb") as f:
                response.jpg_base64 = base64.b64encode(f.read()).decode()

    return response


@router.post("/process/quick")
async def process_quick(
    file: UploadFile = File(...),
    size: int = Form(default=648),
    processor: PhotoProcessor = Depends(get_processor),
):
    """
    Quick processing with sensible defaults.

    Returns the processed image directly (PNG format).
    Ideal for simple integrations.
    """
    import tempfile

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Read file content
    content = await file.read()

    # Create processing options
    from facecraft.processing.processor import ProcessingOptions
    options = ProcessingOptions(
        width=size,
        height=size,
        use_oval_mask=True,
        enhance_face=True,
        enhance_photo=True
    )

    # Process
    png_bytes, _, result = processor.process_image_bytes(content, options)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Processing failed")

    if not png_bytes:
        raise HTTPException(status_code=500, detail="No output generated")

    # Return PNG directly
    from fastapi.responses import Response
    return Response(content=png_bytes, media_type="image/png")


@router.get("/download/{job_id}/{format}")
async def download_processed_photo(
    job_id: str,
    format: str,
    output_dir: Path = Depends(get_output_dir)
):
    """
    Download processed photo.

    **Parameters:**
    - **job_id**: Job ID from processing response
    - **format**: "png" or "jpg"
    """
    job_output_dir = output_dir / job_id

    if not job_output_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    if format == "png":
        png_files = list(job_output_dir.glob("*.png"))
        if not png_files:
            raise HTTPException(status_code=404, detail="PNG file not found")
        return FileResponse(png_files[0], media_type="image/png")

    elif format == "jpg":
        jpg_dir = job_output_dir / "jpg"
        jpg_files = list(jpg_dir.glob("*.jpg")) if jpg_dir.exists() else []
        if not jpg_files:
            raise HTTPException(status_code=404, detail="JPG file not found")
        return FileResponse(jpg_files[0], media_type="image/jpeg")

    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'png' or 'jpg'")


@router.delete("/jobs/{job_id}")
async def cleanup_job(
    job_id: str,
    output_dir: Path = Depends(get_output_dir)
):
    """
    Delete job files to free up space.

    **Parameters:**
    - **job_id**: Job ID to delete
    """
    job_output_dir = output_dir / job_id

    if job_output_dir.exists():
        shutil.rmtree(job_output_dir)
        return {"message": f"Job {job_id} deleted"}

    return {"message": f"Job {job_id} not found"}


@router.post("/process/batch", response_model=BatchResponse)
async def process_batch(
    files: list[UploadFile] = File(...),
    width: int = Form(default=648),
    height: int = Form(default=648),
    return_base64: bool = Form(default=True),
    processor: PhotoProcessor = Depends(get_processor),
    upload_dir: Path = Depends(get_upload_dir),
    output_dir: Path = Depends(get_output_dir),
):
    """
    Process multiple photos at once.

    **Parameters:**
    - **files**: Multiple image files
    - **width/height**: Output dimensions
    - **return_base64**: Include base64 encoded images in response

    **Returns:**
    - Results for each processed image
    - Overall success/failure counts
    """
    start_time = time.time()
    job_id = str(uuid.uuid4())[:8]
    results = []

    from facecraft.processing.processor import ProcessingOptions
    options = ProcessingOptions(
        width=width,
        height=height,
        use_oval_mask=True,
        enhance_face=True,
        enhance_photo=True,
        max_jpeg_size_kb=99
    )

    for idx, file in enumerate(files):
        try:
            # Save file
            upload_path = upload_dir / f"{job_id}_{idx}_{file.filename}"
            with open(upload_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Process
            file_output_dir = output_dir / job_id / Path(file.filename).stem
            file_output_dir.mkdir(parents=True, exist_ok=True)
            output_path = file_output_dir / f"{Path(file.filename).stem}.png"

            result = processor.process_image(str(upload_path), str(output_path), options)

            item = BatchResultItem(
                filename=file.filename,
                success=result.success,
                error=result.error if not result.success else None,
                error_message=result.error if not result.success else None
            )

            if result.success:
                item.download_url = f"/api/v1/download/{job_id}/{Path(file.filename).stem}/png"

            results.append(item)

            # Cleanup upload
            upload_path.unlink(missing_ok=True)

        except Exception as e:
            results.append(BatchResultItem(
                filename=file.filename,
                success=False,
                error="processing_error",
                error_message=str(e)
            ))

    processing_time = int((time.time() - start_time) * 1000)
    successful = sum(1 for r in results if r.success)

    return BatchResponse(
        job_id=job_id,
        total=len(files),
        successful=successful,
        failed=len(files) - successful,
        processing_time_ms=processing_time,
        results=results
    )
