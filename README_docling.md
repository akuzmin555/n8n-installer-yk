# Docling OCR troubleshooting

This note documents the Docling OCR issue observed with Russian OCR in the
`docling` container and the fix applied in this installation.

## Symptom

In the Docling UI at `https://docling.ittelo.biz/ui/`, document conversion
worked when the OCR language field did not include Russian. When `ru` was added
and the OCR engine was set to EasyOCR, the UI returned:

```text
Error processing file(s): Task failed with status 'failure'
```

The container log showed the real cause:

```text
Missing /opt/app-root/src/models/EasyOcr/cyrillic_g2.pth and downloads disabled
```

## Root Cause

The container was using a CUDA-capable Docling image, but the environment still
had `DOCLING_DEVICE=cpu`. This made Docling run inference on CPU even though the
container had GPU access.

After enabling CUDA, EasyOCR itself was available and could download the Russian
models, but Docling Serve jobs did not use EasyOCR's default cache. Because
`DOCLING_SERVE_ARTIFACTS_PATH=/opt/app-root/src/models` is set, Docling expects
OCR artifacts to already exist below that artifacts directory and disables
downloads inside the conversion worker.

As a result:

- Manual EasyOCR test downloaded models to EasyOCR cache:

  ```text
  /opt/app-root/src/.cache/easyocr/model
  ```

- Docling UI looked for EasyOCR artifacts here:

  ```text
  /opt/app-root/src/models/EasyOcr
  ```

The Russian EasyOCR recognition model `cyrillic_g2.pth` existed in the cache
after the manual test, but it was missing from Docling's artifacts path.

## Applied Compose Settings

The GPU override for Docling should include:

```yaml
services:
  docling:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - DOCLING_DEVICE=cuda:0
      - DOCLING_SERVE_ARTIFACTS_PATH=/opt/app-root/src/models
      - EASYOCR_MODULE_PATH=/opt/app-root/src/.cache/easyocr
    volumes:
      - docling_cache:/opt/app-root/src/.cache
      - docling_models:/opt/app-root/src/models
```

`DOCLING_DEVICE=cuda:0` is the important setting for Docling GPU inference.
`EASYOCR_MODULE_PATH` gives manual EasyOCR tests a persistent cache, but Docling
Serve still needs EasyOCR model files under the artifacts path.

## Verification

Check CUDA inside the container:

```bash
sudo docker exec -i docling python - <<'PY'
import os
import torch

print("DOCLING_DEVICE =", os.getenv("DOCLING_DEVICE"))
print("torch =", torch.__version__)
print("cuda_available =", torch.cuda.is_available())
print("cuda_devices =", torch.cuda.device_count())
if torch.cuda.is_available():
    print("cuda_name =", torch.cuda.get_device_name(0))
PY
```

Expected result:

```text
DOCLING_DEVICE = cuda:0
cuda_available = True
```

Download/check EasyOCR Russian + English models:

```bash
sudo docker exec -i docling python - <<'PY'
import easyocr

reader = easyocr.Reader(["ru", "en"], gpu=True, verbose=True)
print("EasyOCR ru+en OK")
PY
```

Copy EasyOCR models from the EasyOCR cache to Docling artifacts:

```bash
sudo docker exec -i docling sh -lc '
mkdir -p /opt/app-root/src/models/EasyOcr
cp -av /opt/app-root/src/.cache/easyocr/model/*.pth /opt/app-root/src/models/EasyOcr/
ls -lh /opt/app-root/src/models/EasyOcr
'
```

Verify that Docling-style local artifacts work with downloads disabled:

```bash
sudo docker exec -i docling python - <<'PY'
import easyocr

reader = easyocr.Reader(
    ["ru", "en"],
    gpu=True,
    model_storage_directory="/opt/app-root/src/models/EasyOcr",
    download_enabled=False,
    verbose=True,
)
print("Docling-style EasyOCR ru+en OK")
PY
```

## Current Container State on This Machine

The currently verified running service is:

```text
container: docling
image: quay.io/docling-project/docling-serve-cu128:v1.8.0-working
docling: 2.60.0
docling-serve: 1.8.0
docling-core: 2.50.0
easyocr: 1.7.2
rapidocr: 3.4.2
```

Important runtime environment values observed inside the container:

```text
DOCLING_DEVICE=cuda:0
DOCLING_SERVE_ARTIFACTS_PATH=/opt/app-root/src/models
DOCLING_SERVE_ENABLE_REMOTE_SERVICES=true
DOCLING_SERVE_ENABLE_UI=1
DOCLING_SERVE_LOAD_MODELS_AT_BOOT=true
EASYOCR_MODULE_PATH=/opt/app-root/src/.cache/easyocr
NVIDIA_VISIBLE_DEVICES=all
```

CUDA is visible from inside the container:

```text
torch cuda True 2
NVIDIA GeForce RTX 4090
```

If `nvidia-smi` shows GPU memory used by the Docling Python process but
`GPU-Util` remains at `0%`, it does not necessarily mean inference is running.
In the observed case, the Docling process was idle while the UI still showed a
processing state. Check the worker log first:

```bash
sudo docker logs --tail=250 docling
```

## VLM Pipeline and Model Selection

In this installed `docling-serve` version, the Gradio UI has a `Pipeline type`
radio button and allows selecting `vlm`, but it does not expose a field for
choosing the VLM model.

The Gradio UI sends only the general conversion options, such as:

```text
pipeline
ocr
ocr_engine
ocr_lang
pdf_backend
table_mode
do_picture_classification
do_picture_description
```

It does not send:

```text
vlm_pipeline_model
vlm_pipeline_model_local
vlm_pipeline_model_api
```

Therefore, when `pipeline=vlm` is selected in the Gradio UI, Docling uses the
default VLM model from the installed Docling Python package. On this version the
default is:

```text
ibm-granite/granite-docling-258M
```

Docling looks for local model artifacts by replacing `/` with `--` under
`DOCLING_SERVE_ARTIFACTS_PATH`. With the current artifacts path, the expected
local directory for the default VLM model is:

```text
/opt/app-root/src/models/ibm-granite--granite-docling-258M
```

At the time of inspection, this default model was not present locally.

The local VLM-related directories that were present were:

```text
/opt/app-root/src/models/HuggingFaceTB--SmolVLM-256M-Instruct
/opt/app-root/src/models/ibm-granite--granite-vision-3.3-2b
```

These models are present on disk, but the current Gradio UI cannot switch to
them. To use them, call the Docling Serve API directly or use the Docling SDK and
pass the model in the request/options.

Example local VLM option for `SmolVLM`:

```json
{
  "vlm_pipeline_model_local": {
    "repo_id": "HuggingFaceTB/SmolVLM-256M-Instruct",
    "response_format": "plaintext",
    "inference_framework": "transformers",
    "transformers_model_type": "automodel-imagetexttotext"
  }
}
```

Example local VLM option for Granite Vision:

```json
{
  "vlm_pipeline_model_local": {
    "repo_id": "ibm-granite/granite-vision-3.3-2b",
    "response_format": "markdown",
    "inference_framework": "transformers",
    "transformers_model_type": "automodel-vision2seq"
  }
}
```

Important: do not pass the artifacts root itself as the model path. This is
wrong:

```text
/opt/app-root/src/models
```

When the artifacts root is treated as a model, the worker can fail with:

```text
Unrecognized processing class in /opt/app-root/src/models. Can't instantiate a
processor, a tokenizer, an image processor or a feature extractor for this
model.
```

Use a concrete model identifier such as `ibm-granite/granite-vision-3.3-2b`, or
download the default UI model `ibm-granite/granite-docling-258M` into the
expected local artifacts directory.

## OCR Models and Engines

Docling supports several OCR engines. The model files are engine-specific.

### RapidOCR

Startup logs like this refer to RapidOCR models:

```text
Using /opt/app-root/src/models/RapidOcr/onnx/PP-OCRv4/det/ch_PP-OCRv4_det_infer.onnx
Using /opt/app-root/src/models/RapidOcr/onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_infer.onnx
Using /opt/app-root/src/models/RapidOcr/onnx/PP-OCRv4/rec/ch_PP-OCRv4_rec_infer.onnx
```

These files are for the RapidOCR engine, typically with the ONNX Runtime
backend:

- `det/...det_infer.onnx`: text detection
- `cls/...cls_infer.onnx`: text orientation/classification
- `rec/...rec_infer.onnx`: text recognition

These are not EasyOCR models. They are used when the Docling job is configured
with RapidOCR, or when an automatic OCR mode selects RapidOCR.

### EasyOCR

EasyOCR uses PyTorch `.pth` files. For Russian + English OCR, the important
files include:

```text
/opt/app-root/src/models/EasyOcr/craft_mlt_25k.pth
/opt/app-root/src/models/EasyOcr/cyrillic_g2.pth
```

`craft_mlt_25k.pth` is the EasyOCR text detector. `cyrillic_g2.pth` is the
EasyOCR recognition model for Cyrillic language groups, including Russian. These
files are used when the Docling UI/API job selects EasyOCR.

### General Docling Models

Other files under `/opt/app-root/src/models` may be Docling pipeline artifacts
for page layout analysis, table structure, picture/classification stages, or
other document conversion steps. Those models are separate from OCR engine
weights and do not replace EasyOCR's `EasyOcr/*.pth` files.

## UI Notes

For EasyOCR Russian OCR, use language codes accepted by EasyOCR:

```text
ru,en
```

or, depending on UI parsing:

```text
ru, en
```

`ru` is the correct EasyOCR code for Russian. If conversion fails again, check:

```bash
sudo docker logs --tail=200 docling
```

The useful error is usually in the worker log before the UI reports the generic
`Task failed with status 'failure'` message.
