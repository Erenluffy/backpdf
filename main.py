"""
FastAPI Backend for PDF Tools
Complete implementation with all endpoints
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from typing import List, Optional, Dict, Any
import os
import uuid
import shutil
import asyncio
from datetime import datetime
import logging
from pathlib import Path
import json

from pdf_processors import PDFProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="kirnim PDF Tools API",
    description="Complete PDF processing API with 30+ tools",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize PDF processor
BASE_DIR = Path("temp_files")
BASE_DIR.mkdir(exist_ok=True)
processor = PDFProcessor(BASE_DIR)

# ==================== HELPER FUNCTIONS ====================

async def save_upload_file(upload_file: UploadFile) -> Path:
    """Save uploaded file and return path"""
    file_id = str(uuid.uuid4())
    file_extension = Path(upload_file.filename).suffix
    file_path = processor.uploads_dir / f"{file_id}{file_extension}"
    
    content = await upload_file.read()
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return file_path

async def save_multiple_files(files: List[UploadFile]) -> List[Path]:
    """Save multiple uploaded files"""
    file_paths = []
    for file in files:
        file_path = await save_upload_file(file)
        file_paths.append(file_path)
    return file_paths

async def cleanup_files(file_paths: List[Path], delay: int = 3600):
    """Delete files after delay"""
    await asyncio.sleep(delay)
    for file_path in file_paths:
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Cleaned up: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

# ==================== HEALTH CHECK ====================

@app.get("/")
async def root():
    return {
        "service": "kirnim PDF Tools API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": "/docs for API documentation"
    }

@app.get("/v1/tools/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "storage": {
            "uploads": len(list(processor.uploads_dir.glob("*"))),
            "processed": len(list(processor.processed_dir.glob("*")))
        }
    }

@app.get("/v1/tools")
async def list_tools():
    """List all available PDF tools"""
    return {
        "tools": [
            # Organize
            {"name": "merge-pdf", "description": "Merge multiple PDFs into one"},
            {"name": "split-pdf", "description": "Split PDF into multiple files"},
            {"name": "remove-pages", "description": "Remove specific pages"},
            {"name": "reorganize-pdf", "description": "Reorder pages"},
            {"name": "extract-pages", "description": "Extract specific pages"},
            {"name": "rotate-pdf", "description": "Rotate pages"},
            {"name": "crop-pdf", "description": "Crop margins"},
            {"name": "compress-pdf", "description": "Reduce file size"},
            {"name": "repair-pdf", "description": "Repair corrupted PDF"},
            {"name": "flatten-pdf", "description": "Remove interactive elements"},
            
            # Convert
            {"name": "pdf-to-word", "description": "Convert to Word document"},
            {"name": "word-to-pdf", "description": "Convert Word to PDF"},
            {"name": "pdf-to-excel", "description": "Convert to Excel spreadsheet"},
            {"name": "pdf-to-pptx", "description": "Convert to PowerPoint"},
            {"name": "pdf-to-jpg", "description": "Convert to JPG images"},
            {"name": "jpg-to-pdf", "description": "Convert JPG to PDF"},
            {"name": "html-to-pdf", "description": "Convert HTML to PDF"},
            {"name": "pdf-to-html", "description": "Convert PDF to HTML"},
            {"name": "pdf-to-text", "description": "Extract text content"},
            
            # Security
            {"name": "protect-pdf", "description": "Add password protection"},
            {"name": "unlock-pdf", "description": "Remove password protection"},
            {"name": "add-watermark", "description": "Add text/image watermark"},
            {"name": "add-page-numbers", "description": "Add page numbers"},
            {"name": "add-metadata", "description": "Add document metadata"},
            {"name": "remove-metadata", "description": "Remove document metadata"},
            
            # Advanced
            {"name": "ocr-pdf", "description": "Perform OCR on scanned PDF"},
            {"name": "extract-text", "description": "Extract text content"},
            {"name": "extract-images", "description": "Extract images"},
            {"name": "compare-pdfs", "description": "Compare two PDFs"},
            {"name": "optimize-pdf", "description": "Optimize for web/print"}
        ]
    }

# ==================== ORGANIZE ENDPOINTS ====================

@app.post("/v1/tools/merge-pdf")
async def merge_pdf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """Merge multiple PDFs into one"""
    try:
        if len(files) < 2:
            raise HTTPException(status_code=400, detail="At least 2 files required")
        
        # Save files
        input_paths = await save_multiple_files(files)
        
        # Process
        output_path = await processor.merge_pdfs(input_paths)
        
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

@app.post("/v1/tools/split-pdf")
async def split_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    split_mode: str = Form("each"),
    ranges: Optional[str] = Form(None)
):
    """Split PDF into multiple files"""
    try:
        input_path = await save_upload_file(file)
        
        output_files = await processor.split_pdf(input_path, split_mode, ranges)
        
        # Create zip file
        zip_path = processor.create_zip(output_files, f"split_{datetime.now().timestamp()}.zip")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_files, [input_path] + output_files + [zip_path])
        
        return FileResponse(
            zip_path,
            media_type='application/zip',
            filename="split_pdf_files.zip"
        )
        
    except Exception as e:
        logger.error(f"Split error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/remove-pages")
async def remove_pages(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    pages_to_remove: str = Form(...)
):
    """Remove specific pages from PDF"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.remove_pages(input_path, pages_to_remove)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="pages_removed.pdf"
        )
        
    except Exception as e:
        logger.error(f"Remove pages error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/reorganize-pdf")
async def reorganize_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    page_order: str = Form(...)
):
    """Reorder PDF pages"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.reorganize_pdf(input_path, page_order)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="reorganized.pdf"
        )
        
    except Exception as e:
        logger.error(f"Reorganize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/extract-pages")
async def extract_pages(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    pages_to_extract: str = Form(...)
):
    """Extract specific pages from PDF"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.extract_pages(input_path, pages_to_extract)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="extracted_pages.pdf"
        )
        
    except Exception as e:
        logger.error(f"Extract pages error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/rotate-pdf")
async def rotate_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    rotation: int = Form(90),
    pages: str = Form("all")
):
    """Rotate PDF pages"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.rotate_pdf(input_path, rotation, pages)
        
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
async def crop_pdf(
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
        input_path = await save_upload_file(file)
        
        margins = {
            'top': margin_top,
            'right': margin_right,
            'bottom': margin_bottom,
            'left': margin_left
        }
        
        output_path = await processor.crop_pdf(input_path, margins, pages)
        
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
async def compress_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    quality: str = Form("medium")
):
    """Compress PDF file size"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.compress_pdf(input_path, quality)
        
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
async def repair_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Repair corrupted PDF"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.repair_pdf(input_path)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="repaired.pdf"
        )
        
    except Exception as e:
        logger.error(f"Repair error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/flatten-pdf")
async def flatten_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Flatten PDF to remove interactive elements"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.flatten_pdf(input_path)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="flattened.pdf"
        )
        
    except Exception as e:
        logger.error(f"Flatten error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CONVERSION ENDPOINTS ====================

@app.post("/v1/tools/pdf-to-word")
async def pdf_to_word(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Convert PDF to Word document"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.pdf_to_word(input_path)
        
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
async def word_to_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Convert Word to PDF"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.word_to_pdf(input_path)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="converted.pdf"
        )
        
    except Exception as e:
        logger.error(f"Word to PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/pdf-to-excel")
async def pdf_to_excel(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Convert PDF to Excel spreadsheet"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.pdf_to_excel(input_path)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename="converted.xlsx"
        )
        
    except Exception as e:
        logger.error(f"PDF to Excel error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/pdf-to-pptx")
async def pdf_to_pptx(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Convert PDF to PowerPoint presentation"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.pdf_to_pptx(input_path)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            filename="converted.pptx"
        )
        
    except Exception as e:
        logger.error(f"PDF to PPTX error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/pdf-to-jpg")
async def pdf_to_jpg(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    quality: int = Form(90),
    dpi: int = Form(150)
):
    """Convert PDF pages to JPG images"""
    try:
        input_path = await save_upload_file(file)
        
        output_files = await processor.pdf_to_jpg(input_path, quality, dpi)
        
        # Create zip file
        zip_path = processor.create_zip(output_files, f"pdf_images_{datetime.now().timestamp()}.zip")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_files, [input_path] + output_files + [zip_path])
        
        return FileResponse(
            zip_path,
            media_type='application/zip',
            filename="pdf_images.zip"
        )
        
    except Exception as e:
        logger.error(f"PDF to JPG error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/jpg-to-pdf")
async def jpg_to_pdf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """Convert JPG images to PDF"""
    try:
        if len(files) < 1:
            raise HTTPException(status_code=400, detail="At least 1 image required")
        
        input_paths = await save_multiple_files(files)
        
        output_path = await processor.jpg_to_pdf(input_paths)
        
        background_tasks.add_task(cleanup_files, input_paths + [output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="converted.pdf"
        )
        
    except Exception as e:
        logger.error(f"JPG to PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/html-to-pdf")
async def html_to_pdf(
    background_tasks: BackgroundTasks,
    url: Optional[str] = Form(None),
    html_content: Optional[str] = Form(None)
):
    """Convert HTML or URL to PDF"""
    try:
        if not url and not html_content:
            raise HTTPException(status_code=400, detail="URL or HTML content required")
        
        output_path = await processor.html_to_pdf(url, html_content)
        
        background_tasks.add_task(cleanup_files, [output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="webpage.pdf"
        )
        
    except Exception as e:
        logger.error(f"HTML to PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/pdf-to-html")
async def pdf_to_html(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Convert PDF to HTML"""
    try:
        input_path = await save_upload_file(file)
        
        # Extract text and create HTML
        text = await processor.extract_text(input_path)
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Converted PDF</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.6; }}
        .content {{ max-width: 800px; margin: 0 auto; }}
    </style>
</head>
<body>
    <div class="content">
        <pre>{text}</pre>
    </div>
</body>
</html>"""
        
        output_path = processor.processed_dir / f"converted_{datetime.now().timestamp()}.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='text/html',
            filename="converted.html"
        )
        
    except Exception as e:
        logger.error(f"PDF to HTML error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/pdf-to-text")
async def pdf_to_text(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Extract text from PDF"""
    try:
        input_path = await save_upload_file(file)
        
        text = await processor.extract_text(input_path)
        
        output_path = processor.processed_dir / f"extracted_{datetime.now().timestamp()}.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='text/plain',
            filename="extracted_text.txt"
        )
        
    except Exception as e:
        logger.error(f"PDF to Text error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SECURITY ENDPOINTS ====================

@app.post("/v1/tools/protect-pdf")
async def protect_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: str = Form(...)
):
    """Add password protection to PDF"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.protect_pdf(input_path, password)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="protected.pdf"
        )
        
    except Exception as e:
        logger.error(f"Protect PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/unlock-pdf")
async def unlock_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: str = Form(...)
):
    """Remove password protection from PDF"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.unlock_pdf(input_path, password)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="unlocked.pdf"
        )
        
    except Exception as e:
        logger.error(f"Unlock PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/add-watermark")
async def add_watermark(
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
        input_path = await save_upload_file(file)
        
        watermark_image_path = None
        if watermark_image:
            watermark_image_path = await save_upload_file(watermark_image)
        
        output_path = await processor.add_watermark(
            input_path, watermark_text, watermark_image_path,
            opacity, position, rotation
        )
        
        cleanup_list = [input_path, output_path]
        if watermark_image_path:
            cleanup_list.append(watermark_image_path)
        
        background_tasks.add_task(cleanup_files, cleanup_list)
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="watermarked.pdf"
        )
        
    except Exception as e:
        logger.error(f"Add watermark error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/add-page-numbers")
async def add_page_numbers(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    position: str = Form("bottom-right"),
    start_number: int = Form(1),
    format: str = Form("1")
):
    """Add page numbers to PDF"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.add_page_numbers(input_path, position, start_number, format)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="numbered.pdf"
        )
        
    except Exception as e:
        logger.error(f"Add page numbers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/add-metadata")
async def add_metadata(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    author: str = Form(""),
    subject: str = Form(""),
    keywords: str = Form("")
):
    """Add metadata to PDF"""
    try:
        input_path = await save_upload_file(file)
        
        metadata = {
            'title': title,
            'author': author,
            'subject': subject,
            'keywords': keywords
        }
        
        output_path = await processor.add_metadata(input_path, metadata)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="with_metadata.pdf"
        )
        
    except Exception as e:
        logger.error(f"Add metadata error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/remove-metadata")
async def remove_metadata(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Remove metadata from PDF"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.remove_metadata(input_path)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="no_metadata.pdf"
        )
        
    except Exception as e:
        logger.error(f"Remove metadata error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ADVANCED ENDPOINTS ====================

@app.post("/v1/tools/ocr-pdf")
async def ocr_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form("eng"),
    dpi: int = Form(300)
):
    """Perform OCR on scanned PDF"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.ocr_pdf(input_path, language, dpi)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="ocr_processed.pdf"
        )
        
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/extract-text")
async def extract_text(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Extract text from PDF"""
    try:
        input_path = await save_upload_file(file)
        
        text = await processor.extract_text(input_path)
        
        background_tasks.add_task(cleanup_files, [input_path])
        
        return JSONResponse({"text": text})
        
    except Exception as e:
        logger.error(f"Extract text error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/extract-images")
async def extract_images(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Extract images from PDF"""
    try:
        input_path = await save_upload_file(file)
        
        output_files = await processor.extract_images(input_path)
        
        # Create zip file
        zip_path = processor.create_zip(output_files, f"extracted_images_{datetime.now().timestamp()}.zip")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_files, [input_path] + output_files + [zip_path])
        
        return FileResponse(
            zip_path,
            media_type='application/zip',
            filename="extracted_images.zip"
        )
        
    except Exception as e:
        logger.error(f"Extract images error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/compare-pdfs")
async def compare_pdfs(
    background_tasks: BackgroundTasks,
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):
    """Compare two PDFs"""
    try:
        input_path1 = await save_upload_file(file1)
        input_path2 = await save_upload_file(file2)
        
        result = await processor.compare_pdfs(input_path1, input_path2)
        
        output_path = Path(result['visual_output'])
        
        background_tasks.add_task(cleanup_files, [input_path1, input_path2, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="comparison.pdf"
        )
        
    except Exception as e:
        logger.error(f"Compare PDFs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/optimize-pdf")
async def optimize_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    level: str = Form("medium")
):
    """Optimize PDF for web or print"""
    try:
        input_path = await save_upload_file(file)
        
        output_path = await processor.optimize_pdf(input_path, level)
        
        background_tasks.add_task(cleanup_files, [input_path, output_path])
        
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename="optimized.pdf"
        )
        
    except Exception as e:
        logger.error(f"Optimize PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== BATCH PROCESSING ====================

@app.post("/v1/tools/batch/compress")
async def batch_compress(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    quality: str = Form("medium")
):
    """Batch compress multiple PDFs"""
    try:
        if len(files) < 1:
            raise HTTPException(status_code=400, detail="At least 1 file required")
        
        input_paths = await save_multiple_files(files)
        output_paths = []
        
        for input_path in input_paths:
            output_path = await processor.compress_pdf(input_path, quality)
            output_paths.append(output_path)
        
        # Create zip with all compressed files
        zip_path = processor.create_zip(output_paths, f"batch_compress_{datetime.now().timestamp()}.zip")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_files, input_paths + output_paths + [zip_path])
        
        return FileResponse(
            zip_path,
            media_type='application/zip',
            filename="compressed_batch.zip"
        )
        
    except Exception as e:
        logger.error(f"Batch compress error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/tools/batch/watermark")
async def batch_watermark(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    watermark_text: str = Form(...),
    opacity: float = Form(0.5),
    position: str = Form("center")
):
    """Batch add watermark to multiple PDFs"""
    try:
        if len(files) < 1:
            raise HTTPException(status_code=400, detail="At least 1 file required")
        
        input_paths = await save_multiple_files(files)
        output_paths = []
        
        for input_path in input_paths:
            output_path = await processor.add_watermark(
                input_path, watermark_text, None, opacity, position, 0
            )
            output_paths.append(output_path)
        
        # Create zip with all watermarked files
        zip_path = processor.create_zip(output_paths, f"batch_watermark_{datetime.now().timestamp()}.zip")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_files, input_paths + output_paths + [zip_path])
        
        return FileResponse(
            zip_path,
            media_type='application/zip',
            filename="watermarked_batch.zip"
        )
        
    except Exception as e:
        logger.error(f"Batch watermark error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
