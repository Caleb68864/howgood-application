# HowGood Application Submission

Small Python integration for submitting a signed application request to a YAML-configured application API.

This repo demonstrates:

- loading API settings and private application details from a local YAML config
- building a deterministic JSON payload
- signing the exact raw request body with HMAC-SHA256
- validating payload data before submission
- keeping the integration simple, testable, and safe to run

## Privacy

Personal application details and live API settings are intentionally not committed to this repository.

The real application data should live in:

```text
application.yaml
```

That file is ignored by git.

A safe placeholder file is included:

```text
application.example.yaml
```

## YAML Config

Only the default path to the config file is defined in the script. API settings and application details are loaded from YAML:

```yaml
api:
  endpoint: "https://example.com/apply"
  defaultSecret: "replace-with-published-secret"
  secretEnvVar: "APPLICATION_HMAC_SECRET"

payload:
  name: "Your Name"
  email: "your.email@example.com"
  resume: "https://example.com/resume.pdf"
  location: "City, State, Country"
  linkedin: "https://www.linkedin.com/in/your-profile/"
  codeLink: "https://github.com/your-username/howgood-application"
  yearsPython: 0
  yearsDjango: 0
  repos: "https://github.com/your-username"
  notes: >-
    Add anything else you would like the application reviewer to know.
```

The signature is calculated from the exact compact JSON body sent to the API.

## Setup

```bash
python -m venv .venv
```

Activate the virtual environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configure Application Details

Copy the example config:

```bash
cp application.example.yaml application.yaml
```

On Windows PowerShell:

```powershell
Copy-Item application.example.yaml application.yaml
```

Edit `application.yaml` with the live API settings and application details.

## Dry Run

The script defaults to dry-run mode.

```bash
python apply_howgood.py
```

To also print the exact compact JSON body that is signed:

```bash
python apply_howgood.py --show-raw-body
```

To use a different config file:

```bash
python apply_howgood.py --config path/to/application.yaml
```

## Submit

```bash
python apply_howgood.py --submit
```

A successful submission should return HTTP `201 Created`.

## Secret Handling

The HMAC secret is read from YAML by default.

For better operational hygiene, set `api.secretEnvVar` in YAML and provide the secret through that environment variable:

```bash
export APPLICATION_HMAC_SECRET="your-secret-here"
python apply_howgood.py --submit
```

PowerShell:

```powershell
$env:APPLICATION_HMAC_SECRET="your-secret-here"
python apply_howgood.py --submit
```

## Tests

Run:

```bash
pytest
```

The tests verify:

- YAML config loading works
- API settings and payload fields validate successfully
- canonical JSON output is deterministic
- HMAC signing matches Python's standard library reference implementation
- environment variable secret overrides work
- common validation failures are caught before submission
