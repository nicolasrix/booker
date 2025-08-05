import os
import fitz  # PyMuPDF
import numpy as np
from PIL import Image
import easyocr
from rich.progress import Progress
from rich.console import Console
import sys
import pickle
import hashlib


def get_cache_filename(pdf_path):
    """Generate a unique cache filename based on PDF content."""
    # Ensure cache directory exists
    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)

    # Get file stats for uniqueness
    stat = os.stat(pdf_path)
    file_info = f"{pdf_path}_{stat.st_size}_{stat.st_mtime}"
    file_hash = hashlib.md5(file_info.encode()).hexdigest()[:8]

    basename = os.path.splitext(os.path.basename(pdf_path))[0]
    return os.path.join(cache_dir, f"ocr_cache_{basename}_{file_hash}.pkl")


def save_ocr_cache(text, pdf_path):
    """Save OCR results to cache file."""
    cache_file = get_cache_filename(pdf_path)
    try:
        with open(cache_file, "wb") as f:
            pickle.dump(text, f)
        return cache_file
    except Exception as e:
        print(f"Warning: Could not save cache: {e}")
        return None


def load_ocr_cache(pdf_path):
    """Load OCR results from cache if available."""
    cache_file = get_cache_filename(pdf_path)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Warning: Could not load cache: {e}")
            # Delete corrupted cache file
            try:
                os.remove(cache_file)
            except:
                pass
    return None


def fix_artificial_linebreaks(text):
    lines = text.split('\n')
    new_lines = []
    for i, line in enumerate(lines):
        # If not the last line, and no punctuation at the end, and next line is lowercase, merge
        if i < len(lines) - 1 and not line.rstrip().endswith(('.', '!', '?')) and lines[i+1] and lines[i+1][0].islower():
            new_lines.append(line.rstrip() + ' ' + lines[i+1].lstrip())
            lines[i+1] = ''
        else:
            new_lines.append(line)
    return '\n'.join([line for line in new_lines if line])


def pdf_to_text(pdf_path, output_dir="output", use_cache=True):
    console = Console()
    os.makedirs(output_dir, exist_ok=True)

    # Try to load from cache first
    if use_cache:
        cached_text = load_ocr_cache(pdf_path)
        if cached_text is not None:
            console.print(f"[green]✓ Loaded OCR results from cache[/green]")
            console.print(f"[blue]Cache file: {get_cache_filename(pdf_path)}[/blue]")
            return cached_text

    console.print("[yellow]No cache found, performing OCR...[/yellow]")

    # Load PDF with PyMuPDF
    pdf = fitz.open(pdf_path)
    reader = easyocr.Reader(['en'])
    all_text = ""

    with Progress() as progress:
        task = progress.add_task("[cyan]OCRing PDF pages...", total=pdf.page_count)

        for page_number in range(pdf.page_count):
            page = pdf.load_page(page_number)
            # Render page to a pixmap (image)
            pix = page.get_pixmap(dpi=300)  # Higher dpi = better OCR, but more RAM
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = reader.readtext(np.array(img), detail=0, paragraph=True)
            all_text += "\n".join(text) + "\n"

            # Update progress immediately
            progress.advance(task)
            progress.refresh()

    # Optional: fix artificial linebreaks
    all_text = fix_artificial_linebreaks(all_text)

    # Save to cache
    if use_cache:
        cache_file = save_ocr_cache(all_text, pdf_path)
        if cache_file:
            console.print(f"[green]✓ OCR results saved to cache: {cache_file}[/green]")

    return all_text


# Utility functions for cache management
def clear_ocr_cache(pdf_path=None):
    """Clear cache files. If pdf_path is provided, clear only that file's cache."""
    cache_dir = "cache"

    if pdf_path:
        cache_file = get_cache_filename(pdf_path)
        if os.path.exists(cache_file):
            os.remove(cache_file)
            print(f"Cleared cache for {pdf_path}")
    else:
        # Clear all cache files in cache/ directory
        if os.path.exists(cache_dir):
            for file in os.listdir(cache_dir):
                if file.startswith('ocr_cache_') and file.endswith('.pkl'):
                    file_path = os.path.join(cache_dir, file)
                    os.remove(file_path)
                    print(f"Removed {file}")


def list_ocr_caches():
    """List all OCR cache files."""
    cache_dir = "cache"

    if os.path.exists(cache_dir):
        cache_files = [f for f in os.listdir(cache_dir) if f.startswith('ocr_cache_') and f.endswith('.pkl')]
        if cache_files:
            print("OCR Cache files:")
            for cache_file in cache_files:
                file_path = os.path.join(cache_dir, cache_file)
                size = os.path.getsize(file_path)
                print(f"  {file_path} ({size:,} bytes)")
        else:
            print("No OCR cache files found in cache/ directory.")
    else:
        print("No cache/ directory found.")