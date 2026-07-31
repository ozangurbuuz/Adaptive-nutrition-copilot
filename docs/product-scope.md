# Product Scope

## Product

Adaptive Nutrition Copilot is a human-in-the-loop personalized nutrition decision-support platform for dietitians and their clients.

The system should help dietitians manage clients, approved meal plans, client restrictions, and dietitian-defined substitution rules. It should help clients request replacements for foods in approved meals while preserving dietitian oversight.

## First MVP Use Case

A dietitian creates a client and meal plan. The client requests a nutritionally similar replacement for one food in an approved meal. The system returns ranked alternatives after applying allergies, client restrictions, and dietitian-defined rules.

## Primary Users

- Dietitian: creates clients, defines restrictions, approves meal plans, configures substitution rules, reviews client activity.
- Client: views approved meals, requests replacement options for a specific food, and may select a low-risk, rule-compliant alternative.
- Admin: manages accounts, roles, and system operations but has no clinical decision authority. Health-data access is denied by default and may only be granted temporarily with justification and audit controls.

## MVP Workflow

1. Dietitian creates a client profile.
2. Dietitian records known allergies and client restrictions.
3. Dietitian creates or records an approved meal plan.
4. Client selects one food in an approved meal and requests alternatives.
5. System identifies candidate alternatives from a trusted food source.
6. System filters candidates by allergy, restriction, and dietitian-defined rules.
7. System ranks remaining alternatives by nutrition similarity.
8. A low-risk, rule-compliant alternative can be selected by the client and is recorded for dietitian review.
9. A risky, rule-conflicting, or indeterminate alternative is not applied without dietitian approval; hard safety violations are blocked.
10. Client sees the allowed result or approval requirement with a clear reason summary.
11. Dietitian can review replacement requests, selected alternatives, blocked results, and approval-required cases.

## In Scope For MVP Definition

- Client creation by dietitian
- Meal plan and meal food modeling
- Replacement request modeling
- Allergy and restriction filtering as configurable records
- Dietitian-defined rule storage
- Ranked replacement response concept
- Auditability of why alternatives were accepted or rejected
- Temporary, justified, time-bounded, and audited Admin support access to health data

## Out Of Scope For Initial Scaffold

- Full application implementation
- LLMs
- RAG
- Vector databases
- Neo4j or graph databases
- Multi-agent architecture
- Fake nutrition data
- Fake medical rules
- Automated diagnosis or treatment recommendations
- Autonomous meal-plan approval

## Assumptions

- Dietitians are responsible for clinical judgment and final policy decisions.
- Nutrition data will come from a trusted external or licensed source selected later.
- Allergy and restriction records are user-specific constraints, not hardcoded medical knowledge.
- Similarity scoring will be transparent and rule-based before any advanced modeling is considered.
- The MVP should preserve an audit trail for safety and accountability.

## Decided Policies

- Rule specificity is `client > plan > global` when applicable rules have the same safety severity.
- Safety severity overrides specificity: `BLOCK > REQUIRE_DIETITIAN_APPROVAL > ALLOW`.
- Authorized dietitians configure substitution tolerances within non-bypassable system safety bounds; the exact threshold values remain to be validated.
- A client can select a low-risk alternative only when it passes all hard constraints and deterministic tolerances.
- Risky, rule-conflicting, or indeterminate changes require dietitian review before application; hard safety violations remain blocked rather than becoming approvable by default.
- Admin health-data access is denied by default. Exceptional access requires a documented reason, approved scope, immutable audit log, start time, and end time.

## Unresolved Decisions

- Which trusted food and nutrient database will be used.
- Exact nutrition-similarity threshold values and their permitted configuration bounds.
- Authentication and authorization provider.
- Regulatory and compliance requirements for target launch regions.
