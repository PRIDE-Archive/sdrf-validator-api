# SDRF Validator API

A FastAPI-based microservice for validating SDRF (Sample and Data Relationship Format) files against proteomics metadata standards.

## Features

- **File Upload Validation**: Upload SDRF files (plain or gzipped) for validation
- **Multiple Templates**: Validate against various templates (human, vertebrates, plants, cell-lines, etc.)
- **Multi-Template Validation**: Validate against multiple templates simultaneously
- **Ontology Validation**: Optional validation of ontology terms against OLS
- **RESTful API**: Simple REST endpoints with OpenAPI documentation

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/templates` | List available validation templates |
| POST | `/validate` | Validate an uploaded SDRF file |
| POST | `/validate/text` | Validate SDRF content as text |
| GET | `/docs` | Swagger UI documentation |
| GET | `/redoc` | ReDoc documentation |

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py

# Or with uvicorn directly
uvicorn app:app --reload --port 5000
```

### Docker

```bash
# Build and run with docker-compose
docker-compose up -d

# Or build manually
docker build -t sdrf-validator-api .
docker run -p 5000:5000 sdrf-validator-api
```

### Kubernetes

Docker image is built and pushed to GitHub Container Registry (GHCR) by CI on push to `main`. Deploy the service and ingress once:

```bash
cd k8s
./deploy.sh
```

The deploy script applies `deployment.yaml` and `ingress-pride-services.yaml` (host `www.ebi.ac.uk`, path `/pride/services/sdrf-validator`). When a new image is pushed, rollout to pick it up:

```bash
kubectl rollout restart deployment/sdrf-validator -n sdrf-validator
```

## Usage Examples

### Validate an SDRF file

```bash
curl -X POST "http://localhost:5000/validate" \
  -F "file=@my_sdrf.tsv" \
  -F "template=default"
```

### Validate with multiple templates

```bash
curl -X POST "http://localhost:5000/validate?template=default&template=human" \
  -F "file=@my_sdrf.tsv"
```

### Validate gzipped file

```bash
curl -X POST "http://localhost:5000/validate" \
  -F "file=@my_sdrf.tsv.gz" \
  -F "template=default"
```

### Get available templates

```bash
curl "http://localhost:5000/templates"
```

### Python client example

```python
import requests

# Upload and validate a file
with open("my_sdrf.tsv", "rb") as f:
    response = requests.post(
        "http://localhost:5000/validate",
        files={"file": f},
        params={"template": ["default", "human"], "skip_ontology": True}
    )

result = response.json()
print(f"Valid: {result['valid']}")
print(f"Errors: {result['error_count']}")
print(f"Warnings: {result['warning_count']}")

for error in result["errors"]:
    print(f"  ERROR: {error['message']}")
```

## Available Templates

| Template | Description |
|----------|-------------|
| `default` / `ms-proteomics` | Standard mass spectrometry proteomics |
| `human` | Human-specific fields |
| `vertebrates` | Vertebrate organisms |
| `invertebrates` | Invertebrate organisms |
| `plants` | Plant-specific fields |
| `cell-lines` | Cell line experiments |
| `base` | Minimal required fields |
| `single-cell` | Single cell proteomics |
| `immunopeptidomics` | Immunopeptidomics experiments |
| `metaproteomics` | Metaproteomics experiments |

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `5000` | Server port |
| `HOST` | `0.0.0.0` | Server host |
| `WORKERS` | `2` | Number of uvicorn workers |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MAX_FILE_SIZE` | `10485760` | Maximum file size in bytes (10MB) |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |

## Response Format

```json
{
  "valid": false,
  "errors": [
    {
      "type": "ERROR",
      "message": "Missing required column: comment[data file]",
      "row": null,
      "column": null
    }
  ],
  "warnings": [
    {
      "type": "WARNING",
      "message": "Ontology term not found in EFO",
      "row": 2,
      "column": "characteristics[disease]"
    }
  ],
  "error_count": 1,
  "warning_count": 1,
  "templates_used": ["default"],
  "sdrf_pipelines_version": "0.0.34"
}
```

## Development

### Running Tests

```bash
pip install pytest httpx
pytest tests/ -v
```

### Building Docker Image

```bash
docker build -t sdrf-validator-api:latest .
```

## License

Apache 2.0
