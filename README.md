# Adaptive Nutrition Copilot

Human-in-the-loop personalized nutrition decision support for dietitians and their clients.

This repository is intentionally at the project-scaffold stage. It defines the monorepo layout, initial product scope, development flow, architecture direction, and data model for the first MVP. It does not yet implement the application.

## MVP Focus

A dietitian creates a client and meal plan. The client requests a nutritionally similar replacement for one food in an approved meal. The system returns ranked alternatives after applying:

- allergies
- client restrictions
- dietitian-defined rules

The MVP keeps the dietitian in control. Replacement results are decision-support suggestions, not autonomous medical advice.

## Repository Structure

```text
adaptive-nutrition-copilot/
  backend/              FastAPI backend placeholder
  frontend/             React frontend placeholder
  db/                   PostgreSQL schema and migration placeholder
  tests/                Cross-project test placeholder
  docs/                 Product and technical documentation
  docker-compose.yml    Local service orchestration placeholder
  .env.example          Local environment variable template
```

## Documentation

- [Product Scope](docs/product-scope.md)
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

The next useful step is to choose concrete backend and frontend package tooling, then add minimal health-check applications and tests.
