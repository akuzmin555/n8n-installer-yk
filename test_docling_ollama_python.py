#!/usr/bin/env python3
"""
Docling with Ollama VLM Integration (Python API)
Converts PDF documents with picture descriptions using Ollama granite3.2-vision model.
"""

import sys
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

# Configuration
PDF_URL = "https://arxiv.org/pdf/2511.16183"  # Test PDF with images
OUTPUT_DIR = Path("/tmp/docling_output")
OUTPUT_DIR.mkdir(exist_ok=True)

print("=" * 80)
print("Docling + Ollama VLM Integration Test")
print("=" * 80)
print(f"\nProcessing: {PDF_URL}")
print(f"Output directory: {OUTPUT_DIR}")
print(f"VLM Model: granite3.2-vision:2b via Ollama")
print("\n" + "-" * 80 + "\n")

# Configure PDF pipeline with picture description
# Note: We're trying API-based approach (if supported in this version)
pipeline_options = PdfPipelineOptions()
pipeline_options.do_picture_description = True
pipeline_options.generate_picture_images = True
pipeline_options.images_scale = 2.0
pipeline_options.enable_remote_services = True  # CRITICAL: Allow Ollama API calls!

# Try to configure API-based VLM (Ollama)
# This may not work if the library version doesn't support it
try:
    from docling.datamodel.pipeline_options import PictureDescriptionApiOptions

    print("✓ PictureDescriptionApiOptions available - configuring Ollama API...")
    pipeline_options.picture_description_options = PictureDescriptionApiOptions(
        url="http://ollama:11434/v1/chat/completions",
        params={"model": "granite3.2-vision:2b", "max_completion_tokens": 200},
        prompt="Describe this image in detail, focusing on key visual elements.",
        timeout=120,
    )
    print("✓ Ollama VLM API configured successfully\n")

except ImportError:
    print("⚠ PictureDescriptionApiOptions not available in this version")
    print("⚠ Trying alternative configuration methods...\n")

    # Fallback: Try using VlmModelApi or other options
    try:
        from docling.datamodel.pipeline_options import VlmModelApi

        print("✓ VlmModelApi available - configuring...")
        vlm_config = VlmModelApi(
            url="http://ollama:11434/v1/chat/completions",
            params={"model": "granite3.2-vision:2b"},
            prompt="Describe this image in detail.",
        )
        # Try to assign it (this may fail if not supported)
        pipeline_options.picture_description_api = vlm_config
        print("✓ VlmModelApi configured\n")

    except (ImportError, AttributeError) as e:
        print(f"⚠ API configuration not supported: {e}")
        print("⚠ Falling back to local SmolVLM (if available)\n")

        # Last resort: use local SmolVLM
        try:
            from docling.datamodel.pipeline_options import smolvlm_picture_description

            print("✓ Using local SmolVLM model...")
            pipeline_options.picture_description_options = smolvlm_picture_description
            pipeline_options.picture_description_options.prompt = (
                "Describe this image in detail, focusing on key visual elements."
            )
            print("✓ SmolVLM configured\n")

        except ImportError:
            print("✗ No VLM options available - descriptions will not be generated")
            pipeline_options.do_picture_description = False

# Create converter with configured options
print("Initializing DocumentConverter...")
converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
        )
    }
)
print("✓ Converter initialized\n")

# Convert the document
print("Starting document conversion (this may take a while)...")
print("  - Downloading PDF...")
print("  - Extracting text and images...")
print("  - Generating picture descriptions...\n")

try:
    result = converter.convert(PDF_URL)
    doc = result.document

    print("✓ Conversion completed successfully!\n")
    print("=" * 80)
    print("Document Statistics:")
    print("=" * 80)
    print(f"  Pages: {len(doc.pages)}")
    print(f"  Pictures: {len(doc.pictures)}")
    print(f"  Tables: {len(doc.tables)}")

    # Save as markdown
    markdown_path = OUTPUT_DIR / "output.md"
    markdown_content = doc.export_to_markdown()
    markdown_path.write_text(markdown_content, encoding="utf-8")
    print(f"\n✓ Markdown saved to: {markdown_path}")

    # Save as JSON
    json_path = OUTPUT_DIR / "output.json"
    json_content = doc.model_dump_json(indent=2)
    json_path.write_text(json_content, encoding="utf-8")
    print(f"✓ JSON saved to: {json_path}")

    # Display picture descriptions
    if doc.pictures:
        print("\n" + "=" * 80)
        print("Picture Descriptions (first 3):")
        print("=" * 80)

        for idx, pic in enumerate(doc.pictures[:3], 1):
            print(f"\n--- Picture {idx} ({pic.self_ref}) ---")
            print(f"Caption: {pic.caption_text(doc=doc)}")

            # Check for annotations with descriptions
            has_description = False
            for annotation in pic.annotations:
                if hasattr(annotation, 'text') and annotation.text:
                    print(f"\nDescription ({annotation.provenance if hasattr(annotation, 'provenance') else 'VLM'}):")
                    # Truncate long descriptions
                    desc_text = annotation.text
                    if len(desc_text) > 300:
                        desc_text = desc_text[:300] + "..."
                    print(desc_text)
                    has_description = True

            if not has_description:
                print("⚠ No VLM description generated for this image")

    print("\n" + "=" * 80)
    print("✓ Processing complete!")
    print("=" * 80)

except Exception as e:
    print(f"\n✗ Error during conversion: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
