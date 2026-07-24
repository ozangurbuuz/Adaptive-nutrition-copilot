# Product Scope

## Product

Adaptive Nutrition Copilot is a human-in-the-loop personalized nutrition decision-support platform for dietitians and their clients.

The system should help dietitians manage clients, approved meal plans, client restrictions, and dietitian-defined substitution rules. It should help clients request replacements for foods in approved meals while preserving dietitian oversight.

## First MVP Use Case

A dietitian creates a client and meal plan. The client requests a nutritionally similar replacement for one food in an approved meal. The system returns ranked alternatives after applying allergies, client restrictions, and dietitian-defined rules.

## Primary Users

- Dietitian: creates clients, defines restrictions, approves meal plans, configures substitution rules, reviews client activity.
- Client: views approved meals and requests replacement options for a specific food.

## MVP Workflow

1. Dietitian creates a client profile.
2. Dietitian records known allergies and client restrictions.
3. Dietitian creates or records an approved meal plan.
4. Client selects one food in an approved meal and requests alternatives.
5. System identifies candidate alternatives from a trusted food source.
6. System filters candidates by allergy, restriction, and dietitian-defined rules.
7. System ranks remaining alternatives by nutrition similarity.
8. Client sees ranked alternatives with clear reason summaries.
9. Dietitian can review replacement requests and selected alternatives.

## In Scope For MVP Definition

- Client creation by dietitian
- Meal plan and meal food modeling
- Replacement request modeling
- Allergy and restriction filtering as configurable records
- Dietitian-defined rule storage
- Ranked replacement response concept
- Auditability of why alternatives were accepted or rejected

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

## Unresolved Decisions

- Which trusted food and nutrient database will be used.
- Whether clients can select replacements directly or only request dietitian approval.
- How strict nutrition similarity thresholds should be, and who configures them.
- Whether dietitian-defined rules apply globally, per client, per condition, or per meal plan.
- Authentication and authorization provider.
- Regulatory and compliance requirements for target launch regions.
