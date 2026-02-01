"""
Unit tests for the UIX Parser module.
"""
import pytest
from src.qa_snapshot_tool.uix_parser import UixParser

class TestUixParser:
    def test_valid_parsing(self):
        """Test parsing of a simple valid XML structure."""
        xml = '<hierarchy><node class="android.widget.Button" bounds="[0,0][100,100]" /></hierarchy>'
        root, error = UixParser.parse(xml)
        
        assert root is not None
        assert not error
        # Parser unwraps <hierarchy>, so root is the <node> itself
        assert root.class_name == "android.widget.Button"
        assert root.valid_bounds is True
        assert root.rect == (0, 0, 100, 100)

    def test_invalid_bounds(self):
        """Test that nodes with invalid bounds are flagged but parsed."""
        xml = '<hierarchy><node bounds="[0,0][-10,-10]" /></hierarchy>'
        root, error = UixParser.parse(xml)
        
        assert root is not None
        # Should be error=True because there are 0 valid nodes
        assert error is True 
        assert root.valid_bounds is False

    def test_malformed_xml(self):
        """Test resilience against bad XML."""
        xml = '<hierarchy><node bounds="...">' # Missing closing tag
        root, error = UixParser.parse(xml)
        
        assert root is None
        assert error is True

    def test_utf8_encoding(self):
        """Test parsing of content with special characters."""
        # "Menü" has a special char
        xml = b'<hierarchy><node text="Men\xc3\xbc" bounds="[0,0][100,100]" /></hierarchy>'
        root, error = UixParser.parse(xml)
        
        assert root is not None
        assert root.text == "Menü"
