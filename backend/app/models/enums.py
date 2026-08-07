from enum import Enum


class BiologicalSex(str, Enum):
    FEMALE = "FEMALE"
    MALE = "MALE"
    INTERSEX = "INTERSEX"


class DietaryPattern(str, Enum):
    OMNIVORE = "OMNIVORE"
    VEGETARIAN = "VEGETARIAN"
    VEGAN = "VEGAN"


class AllergySeverity(str, Enum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class MedicalConditionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"


class MedicationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class NutritionPlanStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class MealType(str, Enum):
    BREAKFAST = "BREAKFAST"
    MORNING_SNACK = "MORNING_SNACK"
    LUNCH = "LUNCH"
    AFTERNOON_SNACK = "AFTERNOON_SNACK"
    DINNER = "DINNER"
    EVENING_SNACK = "EVENING_SNACK"
    OTHER = "OTHER"


class MealItemUnit(str, Enum):
    GRAM = "GRAM"
    MILLILITER = "MILLILITER"
    PIECE = "PIECE"
    PORTION = "PORTION"


class FoodCategory(str, Enum):
    DAIRY = "DAIRY"
    MEAT = "MEAT"
    EGG = "EGG"
    LEGUME = "LEGUME"
    GRAIN = "GRAIN"
    VEGETABLE = "VEGETABLE"
    FRUIT = "FRUIT"
    NUT_SEED = "NUT_SEED"
    FAT_OIL = "FAT_OIL"
    BEVERAGE = "BEVERAGE"
    OTHER = "OTHER"


class NutrientReferenceUnit(str, Enum):
    GRAM = "GRAM"
    MILLILITER = "MILLILITER"
