from enum import Enum


class EntityType(Enum):
    """Enumeration of entity types in a semantic model."""

    PRIMARY = "primary"
    FOREIGN = "foreign"


class Entity:
    """Represents an entity in a semantic model.

    An entity defines a relationship or key constraint in the data model,
    such as primary keys or foreign keys.

    Args:
        name: The name of the entity
        entity_type: The type of entity (primary or foreign)
        column: The column name this entity refers to
        sql: Optional SQL expression for the entity (e.g., a custom join clause
             or derived column expression). Defaults to None.
    """

    def __init__(self, name: str, entity_type: EntityType, column: str, sql: str | None = None):
        self.name = name
        self.entity_type = entity_type
        self.column = column
        self.sql = sql

    def __repr__(self) -> str:
        sql_part = f", sql='{self.sql}'" if self.sql is not None else ""
        return f"Entity(name='{self.name}', entity_type={self.entity_type.value!r}, column='{self.column}'{sql_part})"
