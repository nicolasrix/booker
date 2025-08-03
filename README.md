# 📄 PDF OCR & Text Cleaning Pipeline

A comprehensive Python pipeline that extracts text from PDFs using OCR, cleans it with AI, and generates beautifully formatted output PDFs with proper table handling.

## ✨ Features

- 🔍 **Advanced OCR** with table detection using PyMuPDF + EasyOCR
- 🤖 **AI Text Cleaning** using Ollama (local LLM)
- 📊 **Table Extraction** - Preserves table structure from PDFs
- 📄 **PDF Generation** - Creates clean, formatted PDFs from processed text
- 💾 **Smart Caching** - Avoids re-processing the same files
- 📈 **Progress Tracking** - Rich console output with statistics
- 🔄 **Batch Processing** - Handle multiple PDFs at once

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+**
2. **Ollama** installed and running
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Pull a model (e.g., llama2)
   ollama pull llama2