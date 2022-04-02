[![CodeQL](https://github.com/SG60/ncal/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/SG60/ncal/actions/workflows/codeql-analysis.yml)
[![Package Tests](https://github.com/SG60/ncal/actions/workflows/tests.yml/badge.svg)](https://github.com/SG60/ncal/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/SG60/ncal/branch/main/graph/badge.svg?token=UZCOEA0YWQ)](https://codecov.io/gh/SG60/ncal)
[![Code Style](https://github.com/SG60/ncal/actions/workflows/code-style.yml/badge.svg)](https://github.com/SG60/ncal/actions/workflows/code-style.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=SG60_ncal&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=SG60_ncal)
  
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ncal?label=supported%20python)](https://pypi.org/project/ncal/)
[![PyPI](https://img.shields.io/pypi/v/ncal?logo=python)](https://pypi.org/project/ncal/)
[![Docker Image Version (latest semver)](https://img.shields.io/docker/v/sg60/ncal?label=docker&logo=docker)](https://hub.docker.com/r/sg60/ncal)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# 2-Way Sync for Notion and Google Calendar
  
Currently reworking the documentation.

Install with `pip install ncal`. This will install the `ncal` command.

## Configuration
Configuration is via toml, command line flags, or environment variables (including via a .env file).

Configuration is via toml, command line flags, or environment variables (including via a .env file). Reading through `config.py` will give a lot of useful information on options. Run `ncal --help` to get more info on the cli command.

## Key dependencies
- [Notion API Python SDK](https://github.com/ramnes/notion-sdk-py)
- https://github.com/googleapis/google-api-python-client
- [Arrow](https://github.com/arrow-py/arrow) for datetime handling
- Dev:
  - https://github.com/HypothesisWorks/hypothesis
  - https://github.com/python/mypy
