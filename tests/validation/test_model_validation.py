
import pytest
from unittest.mock import Mock, MagicMock
from pysemantic.validation.model_validation import ModelValidation, ModelValidationError
from pysemantic.modeling import Model

@pytest.fixture
def mock_model():
    m = MagicMock(spec=Model)
    m.name = "valid_name"
    m.table = "valid_table"
    m.primary_key = "valid_pk"
    return m

def test_validate_valid_identifiers(mock_model):
    """Test valid identifiers."""
    validator = ModelValidation(mock_model)
    validator.validate() # Should pass

def test_model_name_reserved_word(mock_model):
    """Test model name cannot be reserved word."""
    mock_model.name = "class"
    validator = ModelValidation(mock_model)
    
    with pytest.raises(ModelValidationError) as exc:
        validator._validate_model_name_is_valid_identifier()
    
    assert "reserved word" in str(exc.value)

def test_model_name_invalid_format(mock_model):
    """Test model name invalid format."""
    mock_model.name = "invalid name"
    validator = ModelValidation(mock_model)
    
    with pytest.raises(ModelValidationError) as exc:
        validator._validate_model_name_is_valid_identifier()
    
    assert "valid identifier" in str(exc.value)

def test_table_name_reserved_word(mock_model):
    """Test table name cannot be reserved word."""
    mock_model.table = "select" # SQL keyword
    validator = ModelValidation(mock_model)
    
    with pytest.raises(ModelValidationError) as exc:
        validator._validate_table_name_is_valid_identifier()
        
    assert "reserved word" in str(exc.value)

def test_table_name_invalid_format(mock_model):
    """Test table name invalid format."""
    mock_model.table = "invalid-table"
    validator = ModelValidation(mock_model)
    
    with pytest.raises(ModelValidationError) as exc:
        validator._validate_table_name_is_valid_identifier()
        
    assert "valid identifier" in str(exc.value)

def test_primary_key_reserved_word(mock_model):
    """Test primary key cannot be reserved word."""
    mock_model.primary_key = "where"
    validator = ModelValidation(mock_model)
    
    with pytest.raises(ModelValidationError) as exc:
        validator._validate_primary_key_is_valid_identifier()
        
    assert "reserved word" in str(exc.value)

def test_primary_key_invalid_format(mock_model):
    """Test primary key invalid format."""
    mock_model.primary_key = "123pk"
    validator = ModelValidation(mock_model)
    
    with pytest.raises(ModelValidationError) as exc:
        validator._validate_primary_key_is_valid_identifier()
        
    assert "valid identifier" in str(exc.value)

def test_empty_identifiers(mock_model):
    """Test empty strings are invalid."""
    validator = ModelValidation(mock_model)
    
    # is_valid_identifier returns False on empty
    assert validator._is_valid_identifier("") is False
    assert validator._is_valid_identifier(None) is False
