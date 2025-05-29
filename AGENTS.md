# Agent instructions

This repository contains an agent for a documentation standardization system.

## Scope

The instructions in this file apply to the entire repository.

## Documentation Standardization

* Every markdown file inside the `docs/` directory must include the following sections in order:
  1. A top-level heading with the document title.
  2. A `Summary` section describing the purpose of the document.
  3. A `References` section if external references are required.

* The agent should run `python doc_standardizer.py` to verify documentation format before creating a pull request.

