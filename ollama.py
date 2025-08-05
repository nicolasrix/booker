import requests
import time
from rich.progress import Progress
from rich.logging import RichHandler
import logging
import re
import os
from datetime import datetime

# Set up console logging (clean, status only)
console_handler = RichHandler(rich_tracebacks=True)
console_handler.setLevel(logging.INFO)

# Set up file logging (detailed)
os.makedirs("logs", exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
file_handler = logging.FileHandler(f"logs/llm_cleaning_{timestamp}.log", encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Set up chunk transformation logging (separate file)
chunk_handler = logging.FileHandler(f"logs/chunk_transformations_{timestamp}.log", encoding='utf-8')
chunk_handler.setLevel(logging.DEBUG)
chunk_formatter = logging.Formatter('%(asctime)s - %(message)s')
chunk_handler.setFormatter(chunk_formatter)

# Main logger
log = logging.getLogger("llm_cleaner")
log.setLevel(logging.DEBUG)
log.addHandler(console_handler)
log.addHandler(file_handler)

# Chunk transformation logger
chunk_log = logging.getLogger("chunk_transforms")
chunk_log.setLevel(logging.DEBUG)
chunk_log.addHandler(chunk_handler)
chunk_log.propagate = False  # Don't send to parent logger

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi3:3.8b"


def check_ollama_connection():
    """Check if Ollama is running and the model is available."""
    try:
        log.info("Checking Ollama connection...")
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
        models = response.json()
        available_models = [model['name'] for model in models.get('models', [])]

        log.info(f"✓ Ollama running with {len(available_models)} models")

        if MODEL not in available_models:
            log.warning(f"Model '{MODEL}' not found. Using first available.")
            if available_models:
                selected_model = available_models[0]
                log.info(f"Selected: {selected_model}")
                return selected_model
            else:
                log.error("No models available!")
                return None

        log.info(f"Using: {MODEL}")
        return MODEL

    except requests.exceptions.ConnectionError:
        log.error("Cannot connect to Ollama. Is it running?")
        return None
    except Exception as e:
        log.error(f"Error checking Ollama: {e}")
        return None


def chunk_text(text, max_chars=600):
    """Yield very small chunks, sentence by sentence."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    log.info(f"Split into {len(sentences)} sentences")

    current_chunk = ''
    chunk_count = 0

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > max_chars and current_chunk:
            chunk_count += 1
            yield current_chunk.strip()
            current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += ' ' + sentence
            else:
                current_chunk = sentence

    if current_chunk:
        chunk_count += 1
        yield current_chunk.strip()

    log.info(f"Created {chunk_count} chunks (max {max_chars} chars)")


def log_chunk_transformation(chunk_num, input_text, output_text, elapsed_time, attempt_num=1):
    """Log detailed chunk transformation to file."""
    separator = "=" * 80

    chunk_log.info(f"\n{separator}")
    chunk_log.info(f"CHUNK {chunk_num} TRANSFORMATION (Attempt {attempt_num})")
    chunk_log.info(f"Processing time: {elapsed_time:.2f} seconds")
    chunk_log.info(f"Input length: {len(input_text)} characters")
    chunk_log.info(f"Output length: {len(output_text)} characters")
    chunk_log.info(f"Length change: {len(output_text) - len(input_text):+d} characters")
    chunk_log.info(f"Length ratio: {len(output_text) / len(input_text) if len(input_text) > 0 else 0:.3f}")
    chunk_log.info(f"{separator}")

    chunk_log.info("INPUT:")
    chunk_log.info(f'"""\n{input_text}\n"""')

    chunk_log.info("OUTPUT:")
    chunk_log.info(f'"""\n{output_text}\n"""')

    # Analysis
    chunk_log.info("ANALYSIS:")

    # Check for specific issues
    issues = []
    if len(output_text) < len(input_text) * 0.7:
        issues.append("WARNING: Output significantly shorter than input")

    if len(output_text) > len(input_text) * 1.5:
        issues.append("WARNING: Output significantly longer than input")

    # Check for common OCR patterns that should be fixed
    ocr_patterns = [
        (r'\b\d+\s+\d+\b', 'Separated numbers'),
        (r'\b[A-Za-z]\s+[A-Za-z]\b', 'Separated letters'),
        (r'[0O](?=\w)', 'Zero/O confusion'),
        (r'[1l](?=\w)', 'One/l confusion'),
    ]

    for pattern, description in ocr_patterns:
        if re.search(pattern, input_text) and not re.search(pattern, output_text):
            issues.append(f"FIXED: {description}")
        elif re.search(pattern, output_text):
            issues.append(f"REMAINING: {description}")

    if issues:
        for issue in issues:
            chunk_log.info(f"  - {issue}")
    else:
        chunk_log.info("  - No issues detected")

    chunk_log.info(f"{separator}\n")


def clean_text_with_ollama(ocr_text):
    working_model = check_ollama_connection()
    if not working_model:
        log.error("Cannot proceed without Ollama connection.")
        return ocr_text

    log.info(f"Starting text cleaning ({len(ocr_text):,} chars)")
    log.info(f"Logs saved to: logs/llm_cleaning_{timestamp}.log")
    log.info(f"Chunk details: logs/chunk_transformations_{timestamp}.log")

    cleaned_chunks = []
    chunks = list(chunk_text(ocr_text))

    # Log session info to chunk file
    chunk_log.info(f"LLM CLEANING SESSION STARTED")
    chunk_log.info(f"Model: {working_model}")
    chunk_log.info(f"Input length: {len(ocr_text):,} characters")
    chunk_log.info(f"Total chunks: {len(chunks)}")
    chunk_log.info(f"Timestamp: {datetime.now()}")

    with Progress() as progress:
        task = progress.add_task("[magenta]Cleaning text chunks...", total=len(chunks))

        for i, chunk in enumerate(chunks):
            chunk_num = i + 1

            progress.update(task, description=f"[magenta]Processing chunk {chunk_num}/{len(chunks)}...")

            prompt = f"""Fix OCR errors in this text. Do NOT summarize or explain anything.

                    EXAMPLE:
                    Input: "Th e qu ick br0wn f0x jum ps 0ver th e 1azy d0g"
                    Output: "The quick brown fox jumps over the lazy dog"
                    
                    Input: "D ata w arehouses ar e lim ited in th eir ab ility"
                    Output: "Data warehouses are limited in their ability"
                    
                    Input: "In 2e21, the c0mpany"
                    Output: "In 2021, the company"
                    
                    IMPORTANT: Keep all years (2020, 2021, 2022, etc.) and numbers exactly as they are.
                    IMPORTANT: Keep ALL line breaks and paragraph breaks as in the input. Do not merge lines or paragraphs. Only correct OCR errors.
                    Now fix this text (output ONLY the corrected text):
                    
                    {chunk}"""

            payload = {
                "model": working_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "top_p": 0.1,
                    "top_k": 10,
                    "repeat_penalty": 1.0,
                    "num_predict": int(len(chunk) * 1.2),
                    "stop": ["\n\nInput:", "EXAMPLE:", "Now fix", "Output:"]
                }
            }

            success = False
            for attempt in range(3):
                try:
                    start_time = time.time()

                    response = requests.post(
                        OLLAMA_URL,
                        json=payload,
                        timeout=60,
                        headers={'Content-Type': 'application/json'}
                    )

                    response.raise_for_status()
                    data = response.json()
                    raw_output = data['response'].strip()

                    elapsed = time.time() - start_time

                    # Clean model response
                    lines = raw_output.split('\n')
                    filtered_lines = []

                    for line in lines:
                        line = line.strip()
                        skip_patterns = [
                            'here is', 'here\'s', 'the text', 'corrected', 'fixed',
                            'output:', 'result:', 'summary', 'main points', 'appears to be'
                        ]

                        if any(pattern in line.lower() for pattern in skip_patterns):
                            continue
                        if line and not line.startswith('*') and not line.startswith('#'):
                            filtered_lines.append(line)

                    cleaned_text = '\n'.join(filtered_lines)

                    # Log detailed transformation
                    log_chunk_transformation(chunk_num, chunk, cleaned_text, elapsed, attempt + 1)

                    # Check if result is reasonable
                    length_ratio = len(cleaned_text) / len(chunk) if len(chunk) > 0 else 0
                    if length_ratio < 0.5:
                        log.warning(f"Chunk {chunk_num}: result too short, using original")
                        cleaned_chunks.append(chunk)
                    else:
                        cleaned_chunks.append(cleaned_text)

                    success = True
                    break

                except Exception as e:
                    log.error(f"Chunk {chunk_num} attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        time.sleep(2)

            if not success:
                log.error(f"Chunk {chunk_num}: all attempts failed, using original")
                cleaned_chunks.append(chunk)

            progress.advance(task)

    final_text = '\n\n'.join(cleaned_chunks)

    # Log session summary
    chunk_log.info(f"\nSESSION SUMMARY")
    chunk_log.info(f"Final length: {len(final_text):,} characters")
    chunk_log.info(f"Length change: {len(final_text) - len(ocr_text):+,} characters")
    chunk_log.info(f"Processing completed: {datetime.now()}")

    log.info(f"✅ Cleaning completed!")
    log.info(f"Length change: {len(final_text) - len(ocr_text):+,} chars")

    return final_text