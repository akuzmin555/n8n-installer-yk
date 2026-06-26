# Ollama Public Access

This note documents how this installation exposes the local Ollama API to the internet without opening Ollama's raw `11434` port publicly.

## Current Setup

Ollama is exposed through Caddy:

```text
internet -> HTTPS 443 -> Caddy -> ollama:11434 inside Docker
```

The public endpoint is:

```text
https://ollama.ittelo.biz
```

The raw Ollama port remains bound only for LAN access in `docker-compose.override.yml`:

```yaml
ports:
  - "192.168.1.143:11434:11434"
```

Do not change this to `0.0.0.0:11434:11434` unless you intentionally want to expose Ollama directly without Caddy protection.

## Caddy Addon

The public Ollama route is defined in:

```text
caddy-addon/ollama.conf
```

Current config:

```caddyfile
{$OLLAMA_HOSTNAME} {
    @authorized header Authorization "Bearer {$OLLAMA_API_TOKEN}"

    handle @authorized {
        reverse_proxy ollama:11434
    }

    handle {
        respond "Unauthorized" 401
    }
}
```

The hostname and bearer token are stored outside Git in:

```text
.env.ollama
```

This file is listed in `.gitignore` and must not be committed.

Example structure:

```dotenv
OLLAMA_HOSTNAME=ollama.ittelo.biz
OLLAMA_API_TOKEN=<secret-token>
```

`docker-compose.override.yml` passes `.env.ollama` only to the Caddy container:

```yaml
caddy:
  env_file:
    - ./.env.ollama
```

The main `Caddyfile` was not changed. It already imports addon configs:

```caddyfile
import /etc/caddy/addons/*.conf
```

The `caddy-addon/` directory is mounted into the Caddy container by Docker Compose, so `caddy-addon/ollama.conf` is loaded automatically after Caddy is restarted.

## DNS

No separate DNS record was needed for `ollama.ittelo.biz` because the domain already has a wildcard DNS record, for example:

```text
*.ittelo.biz -> public server IP
```

The wildcard DNS sends any subdomain to the server. Caddy then decides what to do based on the requested hostname. In this case, requests for `ollama.ittelo.biz` match the site block in `caddy-addon/ollama.conf` and are proxied to `ollama:11434`.

## Client Usage

External clients should use:

```text
https://ollama.ittelo.biz
```

and include this HTTP header:

```text
Authorization: Bearer <OLLAMA_API_TOKEN>
```

Example Python change:

```python
OLLAMA = "https://ollama.ittelo.biz"

headers = {
    "Authorization": "Bearer <OLLAMA_API_TOKEN>",
}

r = requests.post(f"{OLLAMA}/api/chat", json=body, headers=headers, timeout=600)
```

## Verification

Without token, the endpoint should reject the request:

```bash
curl -i https://ollama.ittelo.biz/api/tags
```

Expected result:

```text
401 Unauthorized
```

With token, the endpoint should return Ollama model tags:

```bash
curl https://ollama.ittelo.biz/api/tags \
  -H "Authorization: Bearer <OLLAMA_API_TOKEN>"
```

Expected result:

```text
200 OK
```

with a JSON response containing `models`.

## Regenerate The Token

Generate a new token:

```bash
openssl rand -hex 32
```

Replace the old token in:

```text
.env.ollama
```

Specifically, update `OLLAMA_API_TOKEN`.

Validate the Caddy config:

```bash
docker compose -p localai -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.n8n-workers.yml exec -T caddy caddy validate --config /etc/caddy/Caddyfile
```

Restart Caddy:

```bash
docker compose -p localai -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.n8n-workers.yml restart caddy
```

Update every client script to use the same new token in its `Authorization` header.

## Notes

- This setup protects Ollama at Caddy level. Ollama itself still has no native authentication.
- Caddy obtained and manages the Let's Encrypt certificate for `ollama.ittelo.biz`.
- Long non-streaming Ollama requests are handled directly by Caddy, avoiding Cloudflare proxy timeout risks for `stream=False` workloads.
