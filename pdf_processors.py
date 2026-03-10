# backend/pdf_processors.py
import asyncio
from pathlib import Path
from typing import List, Optional, Union
import logging
import subprocess
import json

# PDF processing libraries
import PyPDF2
from pdf2image import convert_from_path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image
import img2pdf
from wand.image import Image as WandImage
import pytesseract
from docx import Document
from openpyxl import Workbook
from pptx import Presentation

logger = logging.getLogger(__name__)

# ==================== CORE PDF OPERATIONS ====================

async def merge_pdfs(input_paths: List[Path], output_path: Path) -> dict:
    """Merge multiple PDFs into one"""
    try:
        merger = PyPDF2.PdfMerger()
        for path in input_paths:
            merger.append(str(path))
        merger.write(str(output_path))
        merger.close()
        
        return {
            "success": True,
            "output": str(output_path),
            "pages": sum(len(PyPDF2.PdfReader(str(p)).pages) for p in input_paths)
        }
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        raise

async def remove_pages(input_path: Path, output_path: Path, pages_to_remove: List[int]) -> dict:
    """Remove specific pages from PDF"""
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        writer = PyPDF2.PdfWriter()
        
        total_pages = len(reader.pages)
        pages_to_keep = [i for i in range(total_pages) if (i + 1) not in pages_to_remove]
        
        for page_num in pages_to_keep:
            writer.add_page(reader.pages[page_num])
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return {
            "success": True,
            "original_pages": total_pages,
            "removed_pages": len(pages_to_remove),
            "final_pages": len(pages_to_keep)
        }
    except Exception as e:
        logger.error(f"Remove pages failed: {e}")
        raise

async def split_pdf(input_path: Path, output_dir: Path, mode: str, ranges: Optional[str] = None) -> dict:
    """Split PDF into multiple files"""
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        total_pages = len(reader.pages)
        output_files = []
        
        if mode == "each":
            # Split every page
            for i in range(total_pages):
                writer = PyPDF2.PdfWriter()
                writer.add_page(reader.pages[i])
                output_file = output_dir / f"page_{i+1}.pdf"
                with open(output_file, 'wb') as f:
                    writer.write(f)
                output_files.append(str(output_file))
        
        elif mode == "range" and ranges:
            # Split by ranges (e.g., "1-3,4-6,7-9")
            range_list = ranges.split(',')
            for idx, range_str in enumerate(range_list):
                if '-' in range_str:
                    start, end = map(int, range_str.split('-'))
                else:
                    start = end = int(range_str)
                
                writer = PyPDF2.PdfWriter()
                for page_num in range(start - 1, end):
                    if page_num < total_pages:
                        writer.add_page(reader.pages[page_num])
                
                output_file = output_dir / f"split_{idx+1}.pdf"
                with open(output_file, 'wb') as f:
                    writer.write(f)
                output_files.append(str(output_file))
        
        return {
            "success": True,
            "total_pages": total_pages,
            "output_files": output_files,
            "count": len(output_files)
        }
    except Exception as e:
        logger.error(f"Split failed: {e}")
        raise

async def organize_pdf(input_path: Path, output_path: Path, page_order: List[int]) -> dict:
    """Reorder PDF pages"""
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        writer = PyPDF2.PdfWriter()
        
        total_pages = len(reader.pages)
        valid_pages = [p for p in page_order if 1 <= p <= total_pages]
        
        for page_num in valid_pages:
            writer.add_page(reader.pages[page_num - 1])
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return {
            "success": True,
            "original_pages": total_pages,
            "reordered_pages": len(valid_pages)
        }
    except Exception as e:
        logger.error(f"Organize failed: {e}")
        raise

async def rotate_pdf(input_path: Path, output_path: Path, rotation: int, pages: str) -> dict:
    """Rotate PDF pages"""
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        writer = PyPDF2.PdfWriter()
        
        total_pages = len(reader.pages)
        
        if pages == "all":
            target_pages = range(total_pages)
        else:
            target_pages = [int(p.strip()) - 1 for p in pages.split(',')]
        
        for i in range(total_pages):
            page = reader.pages[i]
            if i in target_pages:
                page.rotate(rotation)
            writer.add_page(page)
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return {
            "success": True,
            "rotation": rotation,
            "affected_pages": len(target_pages)
        }
    except Exception as e:
        logger.error(f"Rotate failed: {e}")
        raise

async def crop_pdf(input_path: Path, output_path: Path, 
                   top: float, right: float, bottom: float, left: float,
                   pages: str) -> dict:
    """Crop PDF margins"""
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        writer = PyPDF2.PdfWriter()
        
        total_pages = len(reader.pages)
        
        if pages == "all":
            target_pages = range(total_pages)
        else:
            target_pages = [int(p.strip()) - 1 for p in pages.split(',')]
        
        for i in range(total_pages):
            page = reader.pages[i]
            if i in target_pages:
                # Get original box
                mb = page.mediabox
                
                # Apply crop (simplified - in production use proper box calculations)
                page.mediabox.lower_left = (mb.lower_left[0] + left, mb.lower_left[1] + bottom)
                page.mediabox.upper_right = (mb.upper_right[0] - right, mb.upper_right[1] - top)
            
            writer.add_page(page)
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return {
            "success": True,
            "affected_pages": len(target_pages)
        }
    except Exception as e:
        logger.error(f"Crop failed: {e}")
        raise

async def compress_pdf(input_path: Path, output_path: Path, quality: str) -> dict:
    """Compress PDF using Ghostscript"""
    try:
        quality_settings = {
            "high": "/printer",
            "medium": "/ebook",
            "low": "/screen"
        }
        
        # Use Ghostscript for compression
        cmd = [
            "gs", "-sDEVICE=pdfwrite",
            f"-dPDFSETTINGS={quality_settings[quality]}",
            "-dCompatibilityLevel=1.4",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output_path}",
            str(input_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        original_size = input_path.stat().st_size
        compressed_size = output_path.stat().st_size
        
        return {
            "success": True,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "reduction": f"{(1 - compressed_size/original_size) * 100:.1f}%"
        }
    except Exception as e:
        logger.error(f"Compress failed: {e}")
        raise

async def repair_pdf(input_path: Path, output_path: Path) -> dict:
    """Attempt to repair corrupted PDF"""
    try:
        # Try PyPDF2 first
        try:
            reader = PyPDF2.PdfReader(str(input_path))
            writer = PyPDF2.PdfWriter()
            
            for page in reader.pages:
                writer.add_page(page)
            
            with open(output_path, 'wb') as f:
                writer.write(f)
            
            return {"success": True, "method": "pypdf2"}
        except:
            # Fallback to qpdf
            cmd = ["qpdf", "--replace-input", str(input_path), str(output_path)]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.communicate()
            
            return {"success": True, "method": "qpdf"}
    except Exception as e:
        logger.error(f"Repair failed: {e}")
        raise

# ==================== CONVERSION OPERATIONS ====================

async def convert_to_word(input_path: Path, output_path: Path) -> dict:
    """Convert PDF to Word document"""
    try:
        # Use pdf2docx library
        from pdf2docx import Converter
        
        cv = Converter(str(input_path))
        cv.convert(str(output_path), start=0, end=None)
        cv.close()
        
        return {"success": True, "output": str(output_path)}
    except Exception as e:
        logger.error(f"PDF to Word failed: {e}")
        raise

async def convert_from_word(input_path: Path, output_path: Path) -> dict:
    """Convert Word to PDF"""
    try:
        # Use python-docx and reportlab (simplified - in production use libreoffice)
        doc = Document(str(input_path))
        
        c = canvas.Canvas(str(output_path), pagesize=letter)
        width, height = letter
        
        y = height - 50
        for para in doc.paragraphs:
            c.drawString(50, y, para.text[:50])
            y -= 20
            if y < 50:
                c.showPage()
                y = height - 50
        
        c.save()
        
        return {"success": True, "output": str(output_path)}
    except Exception as e:
        logger.error(f"Word to PDF failed: {e}")
        raise

async def pdf_to_jpg(input_path: Path, output_dir: Path, quality: int, dpi: int) -> dict:
    """Convert PDF pages to JPG images"""
    try:
        images = convert_from_path(
            str(input_path),
            dpi=dpi,
            fmt='jpeg',
            quality=quality
        )
        
        output_files = []
        for i, image in enumerate(images):
            output_file = output_dir / f"page_{i+1}.jpg"
            image.save(output_file, 'JPEG', quality=quality)
            output_files.append(str(output_file))
        
        return {
            "success": True,
            "pages": len(images),
            "output_files": output_files
        }
    except Exception as e:
        logger.error(f"PDF to JPG failed: {e}")
        raise

async def jpg_to_pdf(input_paths: List[Path], output_path: Path, 
                     orientation: str, margin: float) -> dict:
    """Convert JPG images to PDF"""
    try:
        images = []
        for path in input_paths:
            img = Image.open(path)
            if orientation == "landscape" and img.size[0] < img.size[1]:
                img = img.rotate(90, expand=True)
            images.append(img)
        
        # Save as PDF
        if images:
            images[0].save(
                output_path,
                "PDF",
                save_all=True,
                append_images=images[1:],
                quality=95
            )
        
        return {
            "success": True,
            "pages": len(images),
            "output": str(output_path)
        }
    except Exception as e:
        logger.error(f"JPG to PDF failed: {e}")
        raise

# ==================== WATERMARK & SECURITY ====================

async def add_watermark(input_path: Path, output_path: Path,
                        text: Optional[str], image_path: Optional[Path],
                        opacity: float, position: str, rotation: int) -> dict:
    """Add watermark to PDF"""
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        writer = PyPDF2.PdfWriter()
        
        # Create watermark PDF
        watermark_path = Path("temp_watermark.pdf")
        c = canvas.Canvas(str(watermark_path), pagesize=letter)
        
        if text:
            c.setFont("Helvetica", 60)
            c.setFillColorRGB(0.5, 0.5, 0.5, alpha=opacity)
            c.saveState()
            c.translate(300, 400)
            c.rotate(rotation)
            c.drawCentredString(0, 0, text)
            c.restoreState()
        elif image_path:
            # Add image watermark
            c.drawImage(str(image_path), 200, 300, width=200, height=100, 
                       mask='auto', preserveAspectRatio=True)
        
        c.save()
        
        # Merge watermark
        watermark = PyPDF2.PdfReader(str(watermark_path))
        watermark_page = watermark.pages[0]
        
        for page in reader.pages:
            page.merge_page(watermark_page)
            writer.add_page(page)
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        # Cleanup
        watermark_path.unlink()
        
        return {"success": True, "output": str(output_path)}
    except Exception as e:
        logger.error(f"Watermark failed: {e}")
        raise

async def unlock_pdf(input_path: Path, output_path: Path, password: str) -> dict:
    """Remove password protection from PDF"""
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        
        if reader.is_encrypted:
            reader.decrypt(password)
        
        writer = PyPDF2.PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return {"success": True, "output": str(output_path)}
    except Exception as e:
        logger.error(f"Unlock failed: {e}")
        raise

async def protect_pdf(input_path: Path, output_path: Path, 
                      password: str, permissions: str) -> dict:
    """Add password protection to PDF"""
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        writer = PyPDF2.PdfWriter()
        
        for page in reader.pages:
            writer.add_page(page)
        
        # Encrypt with password
        writer.encrypt(password)
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return {"success": True, "output": str(output_path)}
    except Exception as e:
        logger.error(f"Protect failed: {e}")
        raise
async def convert_to_pdfa(input_path: Path, output_path: Path) -> dict:
    """Convert PDF to PDF/A using Ghostscript"""
    try:
        cmd = [
            "gs",
            "-dPDFA=2",
            "-dBATCH",
            "-dNOPAUSE",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-sOutputFile={output_path}",
            str(input_path)
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        await process.communicate()

        return {
            "success": True,
            "output": str(output_path)
        }

    except Exception as e:
        logger.error(f"PDF/A conversion failed: {e}")
        raise
# ==================== ADVANCED FEATURES ====================

async def ocr_pdf(input_path: Path, output_path: Path, language: str, dpi: int) -> dict:
    """Perform OCR on scanned PDF"""
    try:
        # Convert PDF to images
        images = convert_from_path(str(input_path), dpi=dpi)
        
        # Create searchable PDF
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        
        c = canvas.Canvas(str(output_path))
        
        for i, img in enumerate(images):
            # Perform OCR
            text = pytesseract.image_to_string(img, lang=language)
            
            # Add image and text layer
            img_path = f"/tmp/page_{i}.jpg"
            img.save(img_path)
            
            c.drawImage(ImageReader(img_path), 0, 0, width=img.width, height=img.height)
            c.drawString(10, 10, text)  # Simplified - in production create proper text layer
            c.showPage()
        
        c.save()
        
        return {
            "success": True,
            "pages": len(images),
            "language": language
        }
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        raise

async def translate_pdf(input_path: Path, output_path: Path,
                        target_lang: str, source_lang: Optional[str]) -> dict:
    """Translate PDF using AI (simplified)"""
    try:
        # This is a simplified version - in production integrate with Google Translate API or similar
        from googletrans import Translator
        
        translator = Translator()
        reader = PyPDF2.PdfReader(str(input_path))
        writer = PyPDF2.PdfWriter()
        
        translated_texts = []
        
        for page in reader.pages:
            text = page.extract_text()
            if text.strip():
                translated = translator.translate(text, dest=target_lang, src=source_lang)
                translated_texts.append(translated.text)
            else:
                translated_texts.append("")
        
        # Create new PDF with translated text (simplified)
        c = canvas.Canvas(str(output_path))
        for i, text in enumerate(translated_texts):
            c.drawString(50, 750, f"Page {i+1}")
            y = 700
            for line in text.split('\n')[:20]:  # Limit lines
                c.drawString(50, y, line[:80])  # Limit line length
                y -= 15
            c.showPage()
        c.save()
        
        return {
            "success": True,
            "source_language": source_lang or "auto",
            "target_language": target_lang,
            "pages": len(translated_texts)
        }
    except Exception as e:
        logger.error(f"Translate failed: {e}")
        raise

async def compare_pdfs(input_path1: Path, input_path2: Path, output_path: Path) -> dict:
    """Compare two PDFs and highlight differences"""
    try:
        reader1 = PyPDF2.PdfReader(str(input_path1))
        reader2 = PyPDF2.PdfReader(str(input_path2))
        
        # Simplified comparison - in production use difflib or specialized tools
        c = canvas.Canvas(str(output_path))
        
        max_pages = max(len(reader1.pages), len(reader2.pages))
        
        for i in range(max_pages):
            text1 = reader1.pages[i].extract_text() if i < len(reader1.pages) else ""
            text2 = reader2.pages[i].extract_text() if i < len(reader2.pages) else ""
            
            c.drawString(50, 750, f"Page {i+1} Comparison")
            c.drawString(50, 700, "--- PDF 1 ---")
            y = 650
            for line in text1.split('\n')[:10]:
                c.drawString(50, y, line[:60])
                y -= 15
            
            c.drawString(350, 700, "--- PDF 2 ---")
            y = 650
            for line in text2.split('\n')[:10]:
                c.drawString(350, y, line[:60])
                y -= 15
            
            c.showPage()
        
        c.save()
        
        return {
            "success": True,
            "pdf1_pages": len(reader1.pages),
            "pdf2_pages": len(reader2.pages),
            "differences_found": text1 != text2
        }
    except Exception as e:
        logger.error(f"Compare failed: {e}")
        raise

async def html_to_pdf(url: Optional[str] = None, html: Optional[str] = None, 
                      output_path: Optional[Path] = None) -> dict:
    """Convert HTML to PDF using weasyprint or wkhtmltopdf"""
    try:
        from weasyprint import HTML
        
        if url:
            HTML(url).write_pdf(str(output_path))
        elif html:
            HTML(string=html).write_pdf(str(output_path))
        
        return {
            "success": True,
            "output": str(output_path)
        }
    except Exception as e:
        logger.error(f"HTML to PDF failed: {e}")
        raise

# ==================== ADDITIONAL UTILITIES ====================

async def extract_pages(input_path: Path, output_path: Path, pages: List[int]) -> dict:
    """Extract specific pages from PDF"""
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        writer = PyPDF2.PdfWriter()
        
        for page_num in pages:
            if 1 <= page_num <= len(reader.pages):
                writer.add_page(reader.pages[page_num - 1])
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return {
            "success": True,
            "extracted_pages": len(pages),
            "output": str(output_path)
        }
    except Exception as e:
        logger.error(f"Extract pages failed: {e}")
        raise

async def add_page_numbers(input_path: Path, output_path: Path,
                           position: str, start_number: int = 1) -> dict:
    """Add page numbers to PDF"""
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        writer = PyPDF2.PdfWriter()
        
        positions = {
            "bottom-center": (300, 30),
            "bottom-left": (50, 30),
            "bottom-right": (550, 30),
            "top-center": (300, 800),
            "top-left": (50, 800),
            "top-right": (550, 800)
        }
        
        for i, page in enumerate(reader.pages):
            # Create number overlay
            overlay_path = Path(f"/tmp/number_{i}.pdf")
            c = canvas.Canvas(str(overlay_path), pagesize=letter)
            c.setFont("Helvetica", 12)
            x, y = positions.get(position, (300, 30))
            c.drawString(x, y, str(start_number + i))
            c.save()
            
            # Merge
            overlay = PyPDF2.PdfReader(str(overlay_path))
            page.merge_page(overlay.pages[0])
            writer.add_page(page)
            
            overlay_path.unlink()
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return {
            "success": True,
            "pages": len(reader.pages),
            "start_number": start_number
        }
    except Exception as e:
        logger.error(f"Add page numbers failed: {e}")
        raise
