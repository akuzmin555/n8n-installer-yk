#!/bin/bash

# Test Docling with Ollama VLM integration
# Replace YOUR_DOCLING_HOSTNAME, YOUR_USERNAME, YOUR_PASSWORD with real values

echo "Testing Docling with Ollama granite3.2-vision API..."
echo ""

curl -X POST "https://YOUR_DOCLING_HOSTNAME/v1/convert/source/async" \
  -H "Content-Type: application/json" \
  -u "YOUR_USERNAME:YOUR_PASSWORD" \
  -d '{
    "sources": [{
      "kind": "http",
      "url": "https://arxiv.org/pdf/2511.15722"
    }],
    "options": {
      "do_picture_description": true,
      "vlm_pipeline_model_api": {
        "url": "http://ollama:11434/v1/chat/completions",
        "headers": {},
        "params": {
          "model": "granite3.2-vision:2b"
        },
        "timeout": 120,
        "response_format": "json_object",
        "temperature": 0.0
      }
    }
  }'

echo ""
echo ""
echo "Alternative: Test with llama3.2-vision (more powerful)"
echo ""

curl -X POST "https://YOUR_DOCLING_HOSTNAME/v1/convert/source/async" \
  -H "Content-Type: application/json" \
  -u "YOUR_USERNAME:YOUR_PASSWORD" \
  -d '{
    "sources": [{
      "kind": "http",
      "url": "https://arxiv.org/pdf/2511.15722"
    }],
    "options": {
      "do_picture_description": true,
      "vlm_pipeline_model_api": {
        "url": "http://ollama:11434/v1/chat/completions",
        "headers": {},
        "params": {
          "model": "llama3.2-vision"
        },
        "timeout": 120,
        "response_format": "json_object",
        "temperature": 0.0
      }
    }
  }'
