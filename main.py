# backend/main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List, Dict, Any
import os
import uuid
import shutil
import asyncio
from datetime import datetime
import logging
from pathlib import Path

# Import our PDF processors
from pdf_processors import (
    merge_pdfs, split_pdf, remove_pages, organize_pdf,
    rotate_pdf, crop_pdf, compress_pdf, repair_pdf,
    convert_to_pdfa, convert_to_word, convert_to_pptx,
    convert_to_excel, convert_from_word, convert_from_pptx,
    convert_from_excel, pdf_to_jpg, jpg_to_pdf,
    add_watermark, add_page_numbers, sign_pdf,
    unlock_pdf, protect_pdf, redact_pdf,
    ocr_pdf, translate_pdf, compare_pdfs,
    extract_pages, edit_pdf, html_to_pdf,
    scan_to_pdf
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PDFLab API", version="1.0.0")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create temporary directories
BASE_DIR = Path("temp_files")
BASE_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

# Cleanup function for background tasks
async def cleanup_files(file_paths: List[Path], delay: int = 3600):
    """Delete files after delay (default 1 hour)"""
    await asyncio.sleep(delay)
    for file_path in file_paths:
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Cleaned up: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error for {file_path}: {e}")

@app.get("/")
async def root():
    return {
        "service": "PDFLab API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": "/tools/* for all PDF operations"
    }

@app.get("/v1/tools")
async def list_tools():
    """List all available PDF tools"""
    return {
        "tools": [
            "merge-pdf", "split-pdf", "remove-pages", "organize-pdf",
            "rotate-pdf", "crop-pdf", "compress-pdf", "repair-pdf",
            "pdf-to-pdfa", "pdf-to-word", "pdf-to-powerpoint",
            "pdf-to-excel", "word-to-pdf", "powerpoint-to-pdf",
            "excel-to-pdf", "pdf-to-jpg", "jpg-to-pdf", "html-to-pdf",
            "edit-pdf", "sign-pdf", "watermark", "page-numbers",
            "unlock-pdf", "protect-pdf", "redact-pdf", "ocr-pdf",
            "translate-pdf", "compare-pdf", "extract-pages", "scan-to-pdf"
        ],
        "base_url": "/v1/tools/{tool-name}"
    }

# ==================== PDF OPERATIONS ====================

@app.post("/v1/tools/merge-pdf")
async def api_merge_pdf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """Merge multiple PDFs into one"""
    try:
        # Save uploaded files
        input_paths = []
        for file in files:
            file_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            input_paths.append(file_path)
        
        # Process PDF
        output_path = PROCESSED_DIR / f"merged_{uuid.uuid4()}.pdf"
        result = await merge_pdfs(input_paths, output_path)
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_files, input_paths + [output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="merged.pdf"
        )
    except Exception as e:
        logger.error(f"Merge error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/remove-pages")
async def api_remove_pages(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    pages_to_remove: str = Form(...)  # Format: "1,3,5-7"
):
    """Remove specific pages from PDF"""
    try:
        # Parse page ranges
        pages = parse_page_ranges(pages_to_remove)
        
        # Save uploaded file
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process
        output_path = PROCESSED_DIR / f"pages_removed_{uuid.uuid4()}.pdf"
        result = await remove_pages(input_path, output_path, pages)
        
        # Cleanup
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="pages_removed.pdf"
        )
    except Exception as e:
        logger.error(f"Remove pages error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/split-pdf")
async def api_split_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    split_mode: str = Form(...),  # "range" or "each"
    ranges: Optional[str] = Form(None)  # "1-3,4-6,7-9"
):
    """Split PDF into multiple files"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_dir = PROCESSED_DIR / f"split_{uuid.uuid4()}"
        output_dir.mkdir(exist_ok=True)
        
        result = await split_pdf(input_path, output_dir, split_mode, ranges)
        
        # Create zip of all split files
        zip_path = PROCESSED_DIR / f"split_files_{uuid.uuid4()}.zip"
        shutil.make_archive(str(zip_path.with_suffix('')), 'zip', output_dir)
        
        background_tasks.add_task(cleanup_files, [input_path] + list(output_dir.glob("*")) + [zip_path])
        
        return FileResponse(
            zip_path,
            media_type='application/zip',
            filename="split_pdf_files.zip"
        )
    except Exception as e:
        logger.error(f"Split error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/organize-pdf")
async def api_organize_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    page_order: str = Form(...)  # Format: "2,1,3,5,4"
):
    """Reorder PDF pages"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        page_numbers = [int(p.strip()) for p in page_order.split(',')]
        
        output_path = PROCESSED_DIR / f"reorganized_{uuid.uuid4()}.pdf"
        result = await organize_pdf(input_path, output_path, page_numbers)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="reorganized.pdf"
        )
    except Exception as e:
        logger.error(f"Organize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/rotate-pdf")
async def api_rotate_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    rotation: int = Form(...),  # 90, 180, 270
    pages: Optional[str] = Form("all")  # "1,3,5" or "all"
):
    """Rotate PDF pages"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = PROCESSED_DIR / f"rotated_{uuid.uuid4()}.pdf"
        result = await rotate_pdf(input_path, output_path, rotation, pages)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="rotated.pdf"
        )
    except Exception as e:
        logger.error(f"Rotate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/crop-pdf")
async def api_crop_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    margin_top: float = Form(0),
    margin_right: float = Form(0),
    margin_bottom: float = Form(0),
    margin_left: float = Form(0),
    pages: str = Form("all")
):
    """Crop PDF margins"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = PROCESSED_DIR / f"cropped_{uuid.uuid4()}.pdf"
        result = await crop_pdf(
            input_path, output_path,
            margin_top, margin_right, margin_bottom, margin_left,
            pages
        )
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="cropped.pdf"
        )
    except Exception as e:
        logger.error(f"Crop error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/compress-pdf")
async def api_compress_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    quality: str = Form("high")  # "high", "medium", "low"
):
    """Compress PDF file size"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = PROCESSED_DIR / f"compressed_{uuid.uuid4()}.pdf"
        result = await compress_pdf(input_path, output_path, quality)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="compressed.pdf"
        )
    except Exception as e:
        logger.error(f"Compress error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/repair-pdf")
async def api_repair_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Repair corrupted PDF"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = PROCESSED_DIR / f"repaired_{uuid.uuid4()}.pdf"
        result = await repair_pdf(input_path, output_path)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="repaired.pdf"
        )
    except Exception as e:
        logger.error(f"Repair error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/pdf-to-word")
async def api_pdf_to_word(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Convert PDF to Word document"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = PROCESSED_DIR / f"converted_{uuid.uuid4()}.docx"
        result = await convert_to_word(input_path, output_path)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            filename="converted.docx"
        )
    except Exception as e:
        logger.error(f"PDF to Word error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/word-to-pdf")
async def api_word_to_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Convert Word to PDF"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = PROCESSED_DIR / f"converted_{uuid.uuid4()}.pdf"
        result = await convert_from_word(input_path, output_path)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="converted.pdf"
        )
    except Exception as e:
        logger.error(f"Word to PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/pdf-to-jpg")
async def api_pdf_to_jpg(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    quality: int = Form(90),
    dpi: int = Form(150)
):
    """Convert PDF pages to JPG images"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_dir = PROCESSED_DIR / f"images_{uuid.uuid4()}"
        output_dir.mkdir(exist_ok=True)
        
        result = await pdf_to_jpg(input_path, output_dir, quality, dpi)
        
        # Create zip of images
        zip_path = PROCESSED_DIR / f"pdf_images_{uuid.uuid4()}.zip"
        shutil.make_archive(str(zip_path.with_suffix('')), 'zip', output_dir)
        
        background_tasks.add_task(cleanup_files, [input_path] + list(output_dir.glob("*")) + [zip_path])
        
        return FileResponse(
            zip_path,
            media_type='application/zip',
            filename="pdf_images.zip"
        )
    except Exception as e:
        logger.error(f"PDF to JPG error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/jpg-to-pdf")
async def api_jpg_to_pdf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    orientation: str = Form("auto"),
    margin: float = Form(10)
):
    """Convert JPG images to PDF"""
    try:
        input_paths = []
        for file in files:
            file_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            input_paths.append(file_path)
        
        output_path = PROCESSED_DIR / f"converted_{uuid.uuid4()}.pdf"
        result = await jpg_to_pdf(input_paths, output_path, orientation, margin)
        
        background_tasks.add_task(cleanup_files, input_paths + [output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="converted.pdf"
        )
    except Exception as e:
        logger.error(f"JPG to PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/watermark")
async def api_add_watermark(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    watermark_text: Optional[str] = Form(None),
    watermark_image: Optional[UploadFile] = File(None),
    opacity: float = Form(0.5),
    position: str = Form("center"),
    rotation: int = Form(0)
):
    """Add text or image watermark to PDF"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        watermark_path = None
        if watermark_image:
            watermark_path = UPLOAD_DIR / f"watermark_{uuid.uuid4()}_{watermark_image.filename}"
            with open(watermark_path, "wb") as buffer:
                shutil.copyfileobj(watermark_image.file, buffer)
        
        output_path = PROCESSED_DIR / f"watermarked_{uuid.uuid4()}.pdf"
        result = await add_watermark(
            input_path, output_path,
            watermark_text, watermark_path,
            opacity, position, rotation
        )
        
        cleanup_files_list = [input_path, output_path]
        if watermark_path:
            cleanup_files_list.append(watermark_path)
        background_tasks.add_task(cleanup_files, cleanup_files_list)
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="watermarked.pdf"
        )
    except Exception as e:
        logger.error(f"Watermark error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/unlock-pdf")
async def api_unlock_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: str = Form(...)
):
    """Remove password protection from PDF"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = PROCESSED_DIR / f"unlocked_{uuid.uuid4()}.pdf"
        result = await unlock_pdf(input_path, output_path, password)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="unlocked.pdf"
        )
    except Exception as e:
        logger.error(f"Unlock error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/protect-pdf")
async def api_protect_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: str = Form(...),
    permissions: Optional[str] = Form("all")  # "all", "readonly", etc.
):
    """Add password protection to PDF"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = PROCESSED_DIR / f"protected_{uuid.uuid4()}.pdf"
        result = await protect_pdf(input_path, output_path, password, permissions)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="protected.pdf"
        )
    except Exception as e:
        logger.error(f"Protect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/ocr-pdf")
async def api_ocr_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form("eng"),
    dpi: int = Form(300)
):
    """Perform OCR on scanned PDF"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = PROCESSED_DIR / f"ocr_{uuid.uuid4()}.pdf"
        result = await ocr_pdf(input_path, output_path, language, dpi)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="ocr_searchable.pdf"
        )
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/translate-pdf")
async def api_translate_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_language: str = Form(...),
    source_language: Optional[str] = Form(None)
):
    """Translate PDF content using AI"""
    try:
        input_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = PROCESSED_DIR / f"translated_{uuid.uuid4()}.pdf"
        result = await translate_pdf(input_path, output_path, target_language, source_language)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename=f"translated_{target_language}.pdf"
        )
    except Exception as e:
        logger.error(f"Translate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/compare-pdf")
async def api_compare_pdf(
    background_tasks: BackgroundTasks,
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):
    """Compare two PDF files"""
    try:
        input_path1 = UPLOAD_DIR / f"{uuid.uuid4()}_{file1.filename}"
        input_path2 = UPLOAD_DIR / f"{uuid.uuid4()}_{file2.filename}"
        
        with open(input_path1, "wb") as buffer:
            shutil.copyfileobj(file1.file, buffer)
        with open(input_path2, "wb") as buffer:
            shutil.copyfileobj(file2.file, buffer)
        
        output_path = PROCESSED_DIR / f"comparison_{uuid.uuid4()}.pdf"
        result = await compare_pdfs(input_path1, input_path2, output_path)
        
        background_tasks.add_task(cleanup_files, [input_path1, input_path2, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="comparison.pdf"
        )
    except Exception as e:
        logger.error(f"Compare error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/html-to-pdf")
async def api_html_to_pdf(
    background_tasks: BackgroundTasks,
    url: Optional[str] = Form(None),
    html_content: Optional[str] = Form(None)
):
    """Convert HTML or URL to PDF"""
    try:
        output_path = PROCESSED_DIR / f"html_to_pdf_{uuid.uuid4()}.pdf"
        
        if url:
            result = await html_to_pdf(url=url, output_path=output_path)
        elif html_content:
            result = await html_to_pdf(html=html_content, output_path=output_path)
        else:
            raise HTTPException(status_code=400, detail="Either URL or HTML content required")
        
        background_tasks.add_task(cleanup_files, [output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="webpage.pdf"
        )
    except Exception as e:
        logger.error(f"HTML to PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper function to parse page ranges
def parse_page_ranges(range_str: str) -> List[int]:
    """Parse string like '1,3,5-7' into list of page numbers"""
    pages = set()
    for part in range_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    return sorted(pages)

@app.get("/v1/tools/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "storage": {
            "uploads": len(list(UPLOAD_DIR.glob("*"))),
            "processed": len(list(PROCESSED_DIR.glob("*")))
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
