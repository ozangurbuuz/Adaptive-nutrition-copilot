# Data Model

## Purpose

This document defines the conceptual MVP data model. It is not yet a database migration and does not include fake nutrition data or fake medical rules.

## Core Entities

- Dietitian: professional user who manages clients and meal plans.
- Client: person receiving nutrition support from a dietitian.
- Food: food item from a trusted nutrition data source.
- Nutrient Profile: nutrient values associated with a food.
- Meal Plan: dietitian-approved plan assigned to a client.
- Meal: meal within a meal plan.
- Meal Food: specific food and quantity included in a meal.
- Allergy: client-specific allergy record.
- Client Restriction: client-specific dietary restriction or preference.
- Dietitian Rule: configurable rule created by a dietitian.
- Replacement Request: client request to replace one meal food.
- Replacement Candidate: ranked alternative returned for a request.
- Decision Audit: stored explanation of filtering and ranking decisions.

## Mermaid ER Diagram

```mermaid
erDiagram
    DIETITIAN ||--o{ CLIENT : manages
    CLIENT ||--o{ MEAL_PLAN : has
    MEAL_PLAN ||--o{ MEAL : contains
    MEAL ||--o{ MEAL_FOOD : includes
    FOOD ||--o{ MEAL_FOOD : appears_as
    FOOD ||--|| NUTRIENT_PROFILE : has

    CLIENT ||--o{ ALLERGY : records
    CLIENT ||--o{ CLIENT_RESTRICTION : records
    DIETITIAN ||--o{ DIETITIAN_RULE : defines

    MEAL_FOOD ||--o{ REPLACEMENT_REQUEST : replaced_from
    CLIENT ||--o{ REPLACEMENT_REQUEST : creates
    REPLACEMENT_REQUEST ||--o{ REPLACEMENT_CANDIDATE : returns
    FOOD ||--o{ REPLACEMENT_CANDIDATE : suggested_as
    REPLACEMENT_REQUEST ||--|| DECISION_AUDIT : explains

    DIETITIAN {
        uuid id PK
        string email
        string display_name
        datetime created_at
    }

    CLIENT {
        uuid id PK
        uuid dietitian_id FK
        string display_name
        datetime created_at
    }

    FOOD {
        uuid id PK
        string external_source
        string external_id
        string name
        datetime created_at
    }

    NUTRIENT_PROFILE {
        uuid id PK
        uuid food_id FK
        string source_version
        jsonb nutrients
        datetime created_at
    }

    MEAL_PLAN {
        uuid id PK
        uuid client_id FK
        string status
        datetime approved_at
        datetime created_at
    }

    MEAL {
        uuid id PK
        uuid meal_plan_id FK
        string name
        int sort_order
    }

    MEAL_FOOD {
        uuid id PK
        uuid meal_id FK
        uuid food_id FK
        decimal quantity
        string unit
    }

    ALLERGY {
        uuid id PK
        uuid client_id FK
        string label
        string source
        datetime created_at
    }

    CLIENT_RESTRICTION {
        uuid id PK
        uuid client_id FK
        string label
        string restriction_type
        datetime created_at
    }

    DIETITIAN_RULE {
        uuid id PK
        uuid dietitian_id FK
        string name
        string rule_type
        jsonb parameters
        boolean active
    }

    REPLACEMENT_REQUEST {
        uuid id PK
        uuid client_id FK
        uuid meal_food_id FK
        string status
        datetime created_at
    }

    REPLACEMENT_CANDIDATE {
        uuid id PK
        uuid replacement_request_id FK
        uuid food_id FK
        decimal rank_score
        jsonb explanation
    }

    DECISION_AUDIT {
        uuid id PK
        uuid replacement_request_id FK
        jsonb filter_results
        jsonb ranking_inputs
        datetime created_at
    }
```

## Modeling Notes

- `Food` and `Nutrient Profile` depend on a trusted nutrition source selected later.
- `Dietitian Rule.parameters` is intentionally flexible at the conceptual stage, but should become more constrained when rule types are implemented.
- `Decision Audit` should capture enough information to explain why candidates were included, excluded, and ranked.
- Allergies and restrictions are stored as client-specific records. The scaffold does not define clinical interpretation rules.

## Unresolved Decisions

- Exact nutrient schema and units.
- Whether nutrient profiles are versioned per source update.
- Whether allergies and restrictions should reference controlled vocabularies.
- Whether meal-plan approval requires immutable snapshots.
- How replacement candidate explanations should be structured for both clients and dietitians.
