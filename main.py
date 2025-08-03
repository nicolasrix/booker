import pdf_reader
import ollama
import pdf_generator
import os
from rich.console import Console
from datetime import datetime

console = Console()

if __name__ == "__main__":
    console.print("[bold blue]Starting PDF OCR, text cleaning, and PDF generation process...[/bold blue]\n")

    try:
        # Get input file info
        input_pdf = "test_input/test.pdf"
        base_name = os.path.splitext(os.path.basename(input_pdf))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create output directory
        os.makedirs("output", exist_ok=True)

        # Step 1: Extract text from PDF
        console.print("[bold cyan]Step 1: Extracting text from PDF with table detection[/bold cyan]")
        ocr_text = pdf_reader.pdf_to_text(pdf_path=input_pdf)

        # Save raw OCR output
        raw_ocr_file = f"output/{base_name}_raw_ocr_{timestamp}.txt"
        with open(raw_ocr_file, "w", encoding="utf-8") as f:
            f.write(ocr_text)
        console.print(f"[blue]📄 Raw OCR saved to: {raw_ocr_file}[/blue]")

        # Step 2: Clean text with Ollama
        console.print("\n[bold magenta]Step 2: Cleaning text with Ollama[/bold magenta]")
        cleaned_text = ollama.clean_text_with_ollama(ocr_text)

        # Save cleaned text
        cleaned_text_file = f"output/{base_name}_cleaned_{timestamp}.txt"
        with open(cleaned_text_file, "w", encoding="utf-8") as f:
            f.write(cleaned_text)
        console.print(f"[green]📝 Cleaned text saved to: {cleaned_text_file}[/green]")

        # Step 3: Generate PDF from cleaned text
        console.print("\n[bold yellow]Step 3: Generating formatted PDF[/bold yellow]")

        # Create main PDF
        output_pdf = f"output/{base_name}_cleaned_{timestamp}.pdf"
        pdf_title = f"Cleaned Document: {base_name}"

        success = pdf_generator.text_to_pdf(
            text=cleaned_text,
            output_path=output_pdf,
            title=pdf_title
        )

        if success:
            console.print(f"[green]📄 Main PDF created: {output_pdf}[/green]")

            # Create summary PDF
            summary_pdf = f"output/{base_name}_summary_{timestamp}.pdf"
            pdf_generator.create_summary_pdf(
                text=cleaned_text,
                output_path=summary_pdf,
                title=f"Summary: {base_name}"
            )
            console.print(f"[blue]📊 Summary PDF created: {summary_pdf}[/blue]")
        else:
            console.print("[red]❌ PDF generation failed[/red]")

        # Step 4: Show final statistics
        console.print("\n[bold green]📈 Final Statistics[/bold green]")

        # File sizes
        ocr_size = os.path.getsize(raw_ocr_file)
        cleaned_size = os.path.getsize(cleaned_text_file)

        console.print(f"[blue]Raw OCR text:[/blue] {len(ocr_text):,} chars ({ocr_size:,} bytes)")
        console.print(f"[green]Cleaned text:[/green] {len(cleaned_text):,} chars ({cleaned_size:,} bytes)")
        console.print(f"[yellow]Text change:[/yellow] {len(cleaned_text) - len(ocr_text):+,} chars")

        if success and os.path.exists(output_pdf):
            pdf_size = os.path.getsize(output_pdf)
            console.print(f"[magenta]Generated PDF:[/magenta] {pdf_size:,} bytes ({pdf_size / 1024 / 1024:.1f} MB)")

        # Show all output files
        console.print("\n[bold cyan]📁 Output Files Created:[/bold cyan]")
        output_files = [
            (raw_ocr_file, "Raw OCR Text"),
            (cleaned_text_file, "Cleaned Text"),
            (output_pdf, "Main PDF"),
            (summary_pdf, "Summary PDF")
        ]

        for file_path, description in output_files:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                console.print(f"  • {description}: [blue]{file_path}[/blue] ({size:,} bytes)")

        console.print(f"\n[bold green]✅ Complete! All files saved to output/ directory[/bold green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Process interrupted by user[/yellow]")
    except FileNotFoundError as e:
        console.print(f"[bold red]❌ File not found: {e}[/bold red]")
        console.print("[yellow]💡 Make sure your input PDF exists in test_input/test.pdf[/yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        import traceback

        console.print(f"[red]Full error details:[/red]\n{traceback.format_exc()}")


def process_multiple_pdfs(input_dir="test_input", output_dir="output"):
    """Process multiple PDFs in a directory."""
    console.print(f"[bold blue]Processing multiple PDFs from {input_dir}[/bold blue]\n")

    if not os.path.exists(input_dir):
        console.print(f"[red]Input directory {input_dir} does not exist[/red]")
        return

    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]

    if not pdf_files:
        console.print(f"[yellow]No PDF files found in {input_dir}[/yellow]")
        return

    console.print(f"Found {len(pdf_files)} PDF files to process")

    os.makedirs(output_dir, exist_ok=True)

    for i, pdf_file in enumerate(pdf_files, 1):
        console.print(f"\n[bold cyan]Processing {i}/{len(pdf_files)}: {pdf_file}[/bold cyan]")

        try:
            input_path = os.path.join(input_dir, pdf_file)
            base_name = os.path.splitext(pdf_file)[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # OCR
            ocr_text = pdf_reader.pdf_to_text(pdf_path=input_path)

            # Clean
            cleaned_text = ollama.clean_text_with_ollama(ocr_text)

            # Save text
            cleaned_text_file = os.path.join(output_dir, f"{base_name}_cleaned_{timestamp}.txt")
            with open(cleaned_text_file, "w", encoding="utf-8") as f:
                f.write(cleaned_text)

            # Generate PDF
            output_pdf = os.path.join(output_dir, f"{base_name}_cleaned_{timestamp}.pdf")
            pdf_generator.text_to_pdf(cleaned_text, output_pdf, f"Cleaned: {base_name}")

            console.print(f"[green]✅ Completed: {pdf_file}[/green]")

        except Exception as e:
            console.print(f"[red]❌ Failed to process {pdf_file}: {e}[/red]")

    console.print(f"\n[bold green]✅ Batch processing complete![/bold green]")


# Add command line argument support
if __name__ == "__main__" and len(os.sys.argv) > 1:
    if os.sys.argv[1] == "--batch":
        input_dir = os.sys.argv[2] if len(os.sys.argv) > 2 else "test_input"
        output_dir = os.sys.argv[3] if len(os.sys.argv) > 3 else "output"
        process_multiple_pdfs(input_dir, output_dir)