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
    """

    def __init__(self, name: str, entity_type: EntityType, column: str):
        self.name = name
        self.entity_type = entity_type
        self.column = column

    def __repr__(self) -> str:
        return (
            f"Entity(name='{self.name}', "
            f"entity_type={self.entity_type.value!r}, "
            f"column='{self.column}')"
        )
