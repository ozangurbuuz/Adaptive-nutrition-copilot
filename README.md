# Adaptive Nutrition Copilot

Human-in-the-loop personalized nutrition decision support for dietitians and their clients.

This repository is following a gated 13-stage development roadmap. Stage 1 (scope, roles, and architecture boundaries) is approved and closed. A partial FastAPI/database health-check implementation exists, but Stage 2 is not yet complete.

## MVP Focus

A dietitian creates a client and meal plan. The client requests a nutritionally similar replacement for one food in an approved meal. The system returns ranked alternatives after applying:

- allergies
- client restrictions
- dietitian-defined rules

The MVP keeps the dietitian in control. Replacement results are decision-support suggestions, not autonomous medical advice.

## Repository Structure

```text
adaptive-nutrition-copilot/
  backend/              Partial FastAPI backend skeleton
  frontend/             React frontend placeholder
  db/                   PostgreSQL schema and migration placeholder
  tests/                Cross-project test placeholder
  docs/                 Product and technical documentation
  docker-compose.yml    Local service orchestration placeholder
  .env.example          Local environment variable template
```

## Documentation

- [Product Scope](docs/product-scope.md)
- [Roles and Authorization Boundaries](docs/roles.md)
- [Development Flow](docs/development-flow.md)
- [Architecture](docs/architecture.md)
- [Data Model](docs/data-model.md)

## Explicit Non-Goals For This Stage

- No LLM integration
- No RAG pipeline
- No vector database
- No Neo4j or graph database
- No multi-agent architecture
- No fake medical rules
- No fake nutrition data

## Next Step

Complete and verify the Stage 2 FastAPI skeleton acceptance criteria documented in `docs/architecture.md`, without introducing database domain models, LLMs, LangGraph, RAG, or agent tools.
