from pysemantic.modeling import Entity, EntityType


def test_entity_initialization():
    """Test Entity initialization with mandatory arguments."""
    entity = Entity("user", EntityType.PRIMARY, "user_id")
    assert entity.name == "user"
    assert entity.entity_type == EntityType.PRIMARY
    assert entity.column == "user_id"
    assert entity.sql is None


def test_entity_initialization_with_sql():
    """Test Entity initialization with optional sql argument."""
    entity = Entity("user", EntityType.PRIMARY, "user_id", sql="SELECT id FROM users")
    assert entity.name == "user"
    assert entity.entity_type == EntityType.PRIMARY
    assert entity.column == "user_id"
    assert entity.sql == "SELECT id FROM users"


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


def test_entity_repr_with_sql():
    """Test string representation of Entity with sql attribute."""
    entity = Entity("order", EntityType.FOREIGN, "order_id", sql="SELECT id FROM orders")
    expected_repr = "Entity(name='order', entity_type='foreign', column='order_id', sql='SELECT id FROM orders')"
    assert repr(entity) == expected_repr
