"""
File upload and download endpoints for web interface
"""
import os
import hashlib
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from .....services.storage.minio_service import upload_to_minio, download_from_minio
from .....config import settings
from ...schemas import UploadFileResponse

router = APIRouter()


@router.post("/upload", response_model=UploadFileResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a binary/firmware file to MinIO

    Returns:
        UploadFileResponse: Contains the MinIO file path and SHA256 hash
    """
    try:
        # Save uploaded file temporarily
        temp_dir = settings.LOCAL_WORKSPACE_DIR
        os.makedirs(temp_dir, exist_ok=True)

        temp_file_path = os.path.join(temp_dir, file.filename)

        # Read file content and calculate SHA256
        content = await file.read()
        file_sha256 = hashlib.sha256(content).hexdigest()

        # Write file to disk
        with open(temp_file_path, "wb") as buffer:
            buffer.write(content)

        # Upload to MinIO
        minio_path = upload_to_minio(temp_file_path, file.filename, bucket=settings.MINIO_INPUT_BUCKET)

        # Clean up temp file
        try:
            os.remove(temp_file_path)
        except:
            pass

        return UploadFileResponse(
            success=True,
            file_name=file.filename,
            file_path=minio_path,
            file_sha256=file_sha256
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/download")
async def download_file(file_path: str = Query(..., description="MinIO file path")):
    """
    Download a file from MinIO

    Args:
        file_path: The MinIO file path

    Returns:
        FileResponse: The requested file
    """
    try:
        # Download from MinIO
        temp_dir = settings.LOCAL_WORKSPACE_DIR
        os.makedirs(temp_dir, exist_ok=True)

        local_file_path = download_from_minio(file_path, temp_dir, bucket=settings.MINIO_OUTPUT_BUCKET)

        if not os.path.exists(local_file_path):
            raise HTTPException(status_code=404, detail="File not found")

        # Get filename from path
        filename = os.path.basename(file_path)

        return FileResponse(
            path=local_file_path,
            filename=filename,
            media_type='application/octet-stream'
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
