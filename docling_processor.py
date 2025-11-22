#!/usr/bin/env python3
"""
Complete working example for Docling PDF processing with Ollama
Processes PDF file at /home/Ubuntu/mypdfs/docling.pdf using local Ollama with Gemma3 Vision
"""

import os
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline
from docling.datamodel.pipeline_options import (
    VlmPipelineOptions,
    ResponseFormat,
)
from docling.datamodel.pipeline_options_vlm_model import (
    ApiVlmOptions
)

def check_ollama_status():
    """Check if Ollama is running and vision models are available"""
    import subprocess

    try:
        # Check if Ollama container is running and list models
        result = subprocess.run(
            ['docker', 'exec', 'ollama', 'ollama', 'list'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            print("Error: Ollama container is not running")
            print("Please start Ollama with: docker compose -p localai up -d")
            return False

        # Check if vision models are available
        models = result.stdout
        print("✓ Ollama is running in Docker container")
        print("Available models:")
        print(models)

        if any(keyword in models.lower() for keyword in ['llava', 'gemma', 'vision', 'granite']):
            print("✓ Vision models detected!")
            return True
        else:
            print("⚠️  No vision models detected")
            print("\nTo install a vision model, try:")
            print("  docker exec ollama ollama pull llava:7b")
            print("  docker exec ollama ollama pull llava:13b")
            print("  docker exec ollama ollama pull granite3.2-vision:2b")
            return False

    except subprocess.TimeoutExpired:
        print("Error: Ollama command timed out")
        return False

    except FileNotFoundError:
        print("Error: Docker not found. Please ensure Docker is installed")
        return False

    except Exception as e:
        print(f"Error checking Ollama: {str(e)}")
        return False


def main():
    # Path to your PDF file
    pdf_path = "./docling-pdf/2408.09869v5.pdf"

    # Check if file exists
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        print("Please ensure the file exists before running this script.")
        return

    # Check Ollama status
    if not check_ollama_status():
        return

    print(f"Processing PDF file: {pdf_path}")
    print("Setting up Docling converter with Ollama VLM pipeline...")


    # Configure the VLM pipeline options for Ollama using ApiVlmOptions
    model_name = "granite3.2-vision:2b"   # Vision model (7.8 GB) - good balance of size and quality

    # Create ApiVlmOptions for Ollama (OpenAI-compatible API)
    # Use 'localhost' when running on host with exposed port, 'ollama' when in Docker network
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    api_vlm_options = ApiVlmOptions(
        url=f"{ollama_url}/v1/chat/completions",   # Ollama OpenAI-compatible endpoint
        params={
            "model": model_name,
            "max_tokens": 4096,  # Reduced for faster processing
            "temperature": 0.0,
        },
        prompt="Convert this page to markdown. Do not miss any text and only output the bare markdown!",
        timeout=1200,  # Increased timeout to 10 minutes
        scale=1.0,
        response_format=ResponseFormat.MARKDOWN,
    )

    pipeline_options = VlmPipelineOptions(
        vlm_options=api_vlm_options,
        generate_page_images=True,     # Required for VLM processing
        enable_remote_services=True,   # Required for Ollama/API connections
    )

        # Create the document converter with PDF format options
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=pipeline_options,
            ),
        }
    )

    try:
        print(f"Converting PDF document using Ollama model: {model_name}")
        print("This may take a while depending on your system and model size...")

        # Start timing the conversion
        import time
        start_time = time.time()

        # Convert the PDF document
        result = converter.convert(source=pdf_path)
        doc = result.document

        # Calculate conversion time
        conversion_time = time.time() - start_time

        # Print success message
        print(f"\n✓ Conversion completed in {conversion_time:.2f} seconds")
        print(f"Document pages: {len(doc.pages)}")

        # Export to markdown
        markdown_output = doc.export_to_markdown()

        # Save markdown output to file
        output_path = pdf_path.replace('.pdf', '_output.md')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_output)

        print(f"\n✓ Markdown saved to: {output_path}")
        print(f"\nFirst 500 characters of output:")
        print("=" * 80)
        print(markdown_output[:500])
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Error during conversion: {str(e)}")
        print(f"\nFull error details:")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()

