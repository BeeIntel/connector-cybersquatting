# OpenCTI Cybersquatting Domain Connector

This connector periodically downloads domain zone files (`.ru` and `.su`) from the R01 partner feed, extracts domains, filters them according to configurable keywords, and creates `Domain-Name` observables in OpenCTI. It is designed to detect cybersquatting or brand‑related domain registrations.

## Features

- Downloads and processes gzipped domain lists from `https://partner.r01.ru/zones/`.
- Extracts domain names using a robust regex pattern.
- Filters domains by **target substrings** (required) and **exclude substrings** (optional).
- Creates or reuses `Domain-Name` observables in OpenCTI via the GraphQL API.
- Supports scheduling: either at a fixed time of day or at a regular interval (seconds).
- Proxy support (HTTP/HTTPS) and compatibility with OpenCTI 6.x.

## Requirements

- An **OpenCTI** platform instance (accessible via URL and token).
- Python 3.11 (if running outside Docker) – but Docker is the recommended deployment method.
- Docker Engine and Docker Compose (for containerised deployment).

## Configuration (Environment Variables)

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENCTI_URL` | URL of your OpenCTI instance | `http://opencti:8080` |
| `OPENCTI_TOKEN` | token (required) | `2b3f...` |
| `CONNECTOR_ID` | Unique UUID for this connector | `00000000-0000-0000-0000-000000000001` |
| `CONNECTOR_NAME` | Display name in OpenCTI | `Cybersquatting Domain Import` |
| `CONNECTOR_SCOPE` | Observable type this connector handles | `Domain-Name` |
| `CONNECTOR_TYPE` | Must be `EXTERNAL_IMPORT` | `EXTERNAL_IMPORT` |
| `CONNECTOR_CONFIDENCE_LEVEL` | Confidence level for created observables | `75` |
| `CONNECTOR_LOG_LEVEL` | Logging verbosity | `info` |
| `TARGET_SUBSTRINGS` | Comma‑separated keywords – a domain must contain **at least one** of these | `paypal,bank,secure` |
| `EXCLUDE_SUBSTRINGS` | Comma‑separated keywords – domains containing **any** are ignored (optional) | `example,test` |
| `SCHEDULE_INTERVAL` | Run the job every N seconds (overrides `SCHEDULE_TIME`) | `3600` |
| `SCHEDULE_TIME` | Time of day (24h format) when the job runs – only used if `SCHEDULE_INTERVAL` is empty | `03:00` |
| `HTTP_PROXY` / `HTTPS_PROXY` | Proxy URLs (optional) | `http://proxy:3128` |
| `NO_PROXY` | Comma‑separated hosts to bypass proxy | `opencti,rabbitmq` |

> **Note:** The connector always runs once immediately after startup, then follows the defined schedule.

## Building the Docker Image

Build the image:

```bash
docker build -t connector-cybersquatting:latest .
```

## Running with Docker Compose

1. Edit docker-compose.yml and replace all ChangeMe values with your actual configuration.

2. Start the connector:
```bash
docker-compose up -d
```
## Deploying in Portainer

### Option 1: Import the pre‑built image

1. Build the image on a machine with Docker:
```bash
docker build -t connector-cybersquatting:latest .
docker save connector-cybersquatting:latest -o connector-cybersquatting.tar
```

2. In Portainer, go to **Images** → **Import** and upload the `.tar` file.
3. Afterwards, create a **Stack** using the provided `docker-compose.yml` (adjusted with your environment variables).
### Option 2: Build directly inside Portainer

1. In Portainer, navigate to **Images** → **Build image**.
2. Upload the `Dockerfile` and the `src/` folder (or provide a Git repository URL).
3. Tag the image as `connector-cybersquatting:latest`.
4. Go to **Stacks** → **Add stack**, paste the content of `docker-compose.yml` (modify the `image:` line if needed), and deploy.
## Manual Testing (without Docker)

Install dependencies and run the script locally:
```bash
pip install -r src/requirements.txt
export OPENCTI_URL=http://localhost:8080
export OPENCTI_TOKEN=your_token
export TARGET_SUBSTRINGS=paypal
python src/connector.py
```
## Logging

Logs are printed to stdout. You can view them with:
```bash
docker logs connector-cybersquatting
```
Inside Portainer, open the container’s **Logs** panel.

## Troubleshooting

- **No domains created**: Verify that `TARGET_SUBSTRINGS` is not empty and that the downloaded zone files actually contain domains with those keywords.
    
- **Proxy errors**: Ensure `HTTP_PROXY` and `HTTPS_PROXY` are correctly set and that `NO_PROXY` includes your OpenCTI hostname.
    
- **Schedule not working**: Check that `SCHEDULE_INTERVAL` or `SCHEDULE_TIME` is set correctly. If both are missing, the connector will only run once.
