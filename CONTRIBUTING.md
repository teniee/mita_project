# Contributing

Thank you for helping improve MITA! Use the following workflow for pull requests.

## Branch Flow

1. Fork the repository.
2. Create a feature branch from `main`.
3. Open a pull request targeting `main` when your work is ready for review.

## Linting and Tests

Before submitting a PR run:

```bash
ruff check --fix app docs tests
black .
isort .
pytest --cov=app -q
```

Coverage must remain above 65% for the CI gate to pass.

## Running Tests Locally

Install dependencies and run:

```bash
pip install -r requirements.txt
export PYTHONPATH=.
pytest -q
```

## Architecture Diagram

`docs/architecture.puml` contains the high level layout and
`docs/service_interactions.puml` shows how the mobile app interacts with the
API, database and S3. Both diagrams have PNG exports in the same folder.
