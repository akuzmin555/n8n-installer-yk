# Langfuse Traces Export Configuration

## Problem
Langfuse batch export feature was failing with status "Failed" and error message "An internal error occurred" because:
1. Batch export functionality was disabled by default (`LANGFUSE_S3_BATCH_EXPORT_ENABLED=false`)
2. MinIO S3 storage was not accessible via public URL for download links

## Solution Overview
Enable batch export feature and configure MinIO to be accessible through Caddy reverse proxy with proper HTTPS.

## Implementation Steps

### 1. Add Batch Export Variable to Template
Add the following line to `.env.example` after the Langfuse credentials section (around line 113):

```bash
LANGFUSE_S3_BATCH_EXPORT_ENABLED=true
```

### 2. Add MinIO Hostname to Template
Add the following line to `.env.example` in the hostnames section (after `LANGFUSE_HOSTNAME`):

```bash
MINIO_LANGFUSE_HOSTNAME=minio-langfuse.yourdomain.com
```

### 3. Create Caddy Configuration for MinIO
Create file `caddy/custom/minio.caddy` with the following content:

```caddy
# MinIO S3 Storage for Langfuse Batch Exports
# This file is imported by the main Caddyfile and will NOT be affected by updates

{$MINIO_LANGFUSE_HOSTNAME} {
    # Reverse proxy to MinIO S3 API (port 9000)
    reverse_proxy minio:9000

    # Enable gzip compression
    encode gzip

    # Access logging
    log {
        output file /var/log/caddy/minio-access.log {
            roll_size 100mb
            roll_keep 5
            roll_keep_for 720h
        }
        format json
    }

    # Large file support for exports
    request_body {
        max_size 500MB
    }

    # Headers for S3 compatibility
    header {
        # Enable HSTS
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"

        # Prevent MIME type sniffing
        X-Content-Type-Options "nosniff"

        # Remove server header
        -Server
    }
}
```

### 4. Update Docker Compose Override
Add or update sections in `docker-compose.override.yml`:

#### 4.1. Add MinIO Hostname Variable to Caddy

```yaml
services:
  caddy:
    volumes:
      - ./caddy/custom:/etc/caddy/custom:ro
    environment:
      - MINIO_LANGFUSE_HOSTNAME=${MINIO_LANGFUSE_HOSTNAME}
```

#### 4.2. Enable Batch Export for Langfuse

```yaml
  # Langfuse - Enable batch export functionality with MinIO via Caddy
  langfuse-worker:
    environment:
      LANGFUSE_S3_BATCH_EXPORT_ENABLED: true
      LANGFUSE_S3_BATCH_EXPORT_EXTERNAL_ENDPOINT: https://${MINIO_LANGFUSE_HOSTNAME}

  langfuse-web:
    environment:
      LANGFUSE_S3_BATCH_EXPORT_ENABLED: true
      LANGFUSE_S3_BATCH_EXPORT_EXTERNAL_ENDPOINT: https://${MINIO_LANGFUSE_HOSTNAME}
```

### 5. Configure Environment Variables
Add to your `.env` file:

```bash
MINIO_LANGFUSE_HOSTNAME=minio-langfuse.ittelo.biz
```

Note: If you have wildcard DNS (`*.yourdomain.com`), no additional DNS configuration is needed.

### 6. Restart Services
Restart affected containers to apply changes:

```bash
# Restart Caddy to load new configuration
sudo docker compose -p localai up -d --no-deps --force-recreate caddy

# Restart Langfuse services
sudo docker compose -p localai up -d --no-deps --force-recreate langfuse-web langfuse-worker
```

### 7. Verify Configuration

#### 7.1. Check Caddy Status
```bash
docker compose -p localai ps caddy
# Should show: Up X minutes (healthy)
```

#### 7.2. Verify Environment Variables
```bash
sudo docker compose -p localai exec langfuse-worker env | grep BATCH_EXPORT
```

Expected output:
```
LANGFUSE_S3_BATCH_EXPORT_ENABLED=true
LANGFUSE_S3_BATCH_EXPORT_EXTERNAL_ENDPOINT=https://minio-langfuse.ittelo.biz
LANGFUSE_S3_BATCH_EXPORT_BUCKET=langfuse
LANGFUSE_S3_BATCH_EXPORT_PREFIX=exports/
...
```

#### 7.3. Check Caddy Logs
```bash
sudo docker compose -p localai logs caddy | grep minio
```

Should show successful certificate acquisition for `minio-langfuse.yourdomain.com`.

### 8. Test Batch Export
1. Open Langfuse web interface: `https://langfuse.yourdomain.com`
2. Navigate to project settings or traces page
3. Click "Export" or "Batch Export"
4. Wait for export to complete (status should be "Completed")
5. Click "Download" - file should download successfully via `https://minio-langfuse.yourdomain.com/langfuse/exports/...`

## Architecture

```
Browser → Caddy (HTTPS) → MinIO (Internal: minio:9000)
                      ↓
          Download URL: https://minio-langfuse.yourdomain.com/langfuse/exports/file.jsonl
```

## Key Points

1. **Clean Main Branch**: All configuration is in `docker-compose.override.yml` and `caddy/custom/`, which are not affected by upstream updates
2. **Automatic HTTPS**: Caddy automatically obtains Let's Encrypt certificates for the MinIO hostname
3. **Wildcard DNS**: If you have `*.yourdomain.com` pointing to your server, no additional DNS records needed
4. **S3 Compatibility**: MinIO provides S3-compatible API, export files are stored in `langfuse/exports/` bucket prefix

## Troubleshooting

### Export Status Shows "Failed"
- Check worker logs: `sudo docker compose -p localai logs langfuse-worker --tail=50`
- Ensure `LANGFUSE_S3_BATCH_EXPORT_ENABLED=true` is set
- Verify MinIO container is healthy: `docker compose -p localai ps minio`

### Download Links Point to localhost:9090
- Verify `LANGFUSE_S3_BATCH_EXPORT_EXTERNAL_ENDPOINT` is set correctly
- Restart langfuse-worker and langfuse-web containers

### Caddy Won't Start / Restarts Continuously
- Check if `MINIO_LANGFUSE_HOSTNAME` variable is passed to Caddy container
- Verify syntax in `caddy/custom/minio.caddy`
- Check logs: `sudo docker compose -p localai logs caddy --tail=50`

### SSL Certificate Issues
- Ensure DNS record for `minio-langfuse.yourdomain.com` resolves to correct IP
- Check firewall allows ports 80/443
- View certificate status: `docker compose -p localai exec caddy caddy list-certificates`

## Related Files
- `docker-compose.override.yml` - Service overrides
- `caddy/custom/minio.caddy` - MinIO reverse proxy configuration
- `.env` - Environment variables (git-ignored)
- `.env.example` - Template with default values

## References
- [Langfuse Self-Hosting Blob Storage](https://langfuse.com/self-hosting/infrastructure/blobstorage#batch-exports)
- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
- [Caddy Reverse Proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
