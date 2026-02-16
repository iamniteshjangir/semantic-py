from pysemantic.modeling import Entity, EntityType


def test_entity_initialization():
    """Test Entity initialization with mandatory arguments."""
    entity = Entity("user", EntityType.PRIMARY, "user_id")
    assert entity.name == "user"
    assert entity.entity_type == EntityType.PRIMARY
    assert entity.column == "user_id"


def test_entity_type_enum():
    """Test usage of EntityType enum values."""
    assert EntityType.PRIMARY.value == "primary"
    assert EntityType.FOREIGN.value == "foreign"


def test_entity_repr():
    """Test string representation of Entity."""
    # Note: formatting depends on enum repr
    entity = Entity("order", EntityType.FOREIGN, "order_id")
    expected_repr = "Entity(name='order', entity_type='foreign', column='order_id')"
    # Adjust if enum repr is used directly (e.g. <EntityType.FOREIGN: 'foreign'>)
    # Based on source code: f"..., entity_type={self.entity_type.value!r}, ..."
    # So it should result in 'foreign' (quoted string)
    assert repr(entity) == expected_repr
