import importlib
import uuid

import pytest
from sqlalchemy.sql import Select

from app.models.nutrition_plan import NutritionPlan


class _ReadResult:
    def __init__(self, value) -> None:
        self.value = value

    def unique(self):
        return self

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self.value

    def one_or_none(self):
        return self.value

    def first(self):
        return self.value


class _SessionSpy:
    def __init__(self, value=None) -> None:
        self.value = value
        self.statements = []
        self.get_calls = []
        self.write_calls = []

    def execute(self, statement):
        self.statements.append(statement)
        return _ReadResult(self.value)

    def scalar(self, statement):
        self.statements.append(statement)
        return self.value

    def scalars(self, statement):
        self.statements.append(statement)
        return _ReadResult(self.value)

    def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        return self.value

    def add(self, *args, **kwargs) -> None:
        self.write_calls.append("add")

    def add_all(self, *args, **kwargs) -> None:
        self.write_calls.append("add_all")

    def commit(self) -> None:
        self.write_calls.append("commit")

    def flush(self) -> None:
        self.write_calls.append("flush")

    def delete(self, *args, **kwargs) -> None:
        self.write_calls.append("delete")


def _plan_reader():
    try:
        module = importlib.import_module("app.repositories.nutrition_plan")
    except ModuleNotFoundError:
        pytest.fail(
            "app.repositories.nutrition_plan is required for the detail endpoint",
            pytrace=False,
        )

    reader = getattr(module, "get_nutrition_plan_by_id", None)
    assert callable(reader), "get_nutrition_plan_by_id repository function is missing"
    return reader


def _loader_paths(options) -> set[tuple[str, ...]]:
    return {
        tuple(
            part.key
            for part in option.path
            if getattr(part, "key", None) is not None
        )
        for option in options
    }


def test_get_by_id_returns_orm_plan_and_eager_loads_content_without_food() -> None:
    reader = _plan_reader()
    plan = NutritionPlan(title="Repository plan")
    session = _SessionSpy(plan)
    plan_id = uuid.uuid4()

    result = reader(session, plan_id)

    assert result is plan

    if session.get_calls:
        args, kwargs = session.get_calls[0]
        assert plan_id in args
        options = kwargs.get("options", ())
    else:
        assert len(session.statements) == 1
        statement = session.statements[0]
        assert isinstance(statement, Select)
        assert plan_id in statement.compile().params.values()
        options = statement._with_options

    paths = _loader_paths(options)
    assert ("plan_days", "meals", "items") in paths
    assert all("food" not in path for path in paths)


def test_get_by_id_returns_none_without_writing_or_raising_not_found() -> None:
    reader = _plan_reader()
    session = _SessionSpy()

    result = reader(session, uuid.uuid4())

    assert result is None
    assert session.write_calls == []
    assert all(isinstance(statement, Select) for statement in session.statements)
