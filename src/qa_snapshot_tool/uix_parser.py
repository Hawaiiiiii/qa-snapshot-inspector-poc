"""
UI XML Parser Module.

This module is responsible for parsing raw Android UIAutomator XML dumps into a structured
tree of `UiNode` objects. It handles bounds parsing, validation, and tree traversal.
"""

import xml.etree.ElementTree as ET
import re
import hashlib
from typing import Optional, List, Tuple, Union, Any

class UiNode:
    """
    Represents a single UI element in the Android view hierarchy.
    """
    def __init__(self, element: ET.Element, parent: Optional['UiNode'] = None):
        """
        initializes a UiNode from an XML element.

        Args:
            element (ET.Element): The raw XML element.
            parent (Optional[UiNode]): The parent node in the logical tree.
        """
        self.element: ET.Element = element
        self.parent: Optional['UiNode'] = parent
        self.children: List['UiNode'] = []
        
        # String Attributes
        self.text: str = element.get('text', '')
        self.resource_id: str = element.get('resource-id', '')
        self.class_name: str = element.get('class', '')
        self.package: str = element.get('package', '')
        self.content_desc: str = element.get('content-desc', '')
        self.index: str = element.get('index', '0')
        
        # Boolean Flags (Crucial for validation and filtering)
        self.checkable: bool = element.get('checkable', 'false') == 'true'
        self.checked: bool = element.get('checked', 'false') == 'true'
        self.clickable: bool = element.get('clickable', 'false') == 'true'
        self.enabled: bool = element.get('enabled', 'false') == 'true'
        self.focusable: bool = element.get('focusable', 'false') == 'true'
        self.focused: bool = element.get('focused', 'false') == 'true'
        self.scrollable: bool = element.get('scrollable', 'false') == 'true'
        self.long_clickable: bool = element.get('long-clickable', 'false') == 'true'
        self.password: bool = element.get('password', 'false') == 'true'
        self.selected: bool = element.get('selected', 'false') == 'true'
        
        # NAF (Not A Focusable) Logic - often indicates layout wrappers
        self.naf: bool = element.get('NAF', 'false') == 'true'
        if not self.text and not self.resource_id and not self.content_desc:
            self.naf = True

        # Bounds Parsing
        # Standard format: "[x1,y1][x2,y2]"
        self.bounds_str: str = element.get('bounds', '[0,0][0,0]')
        self.rect: Tuple[int, int, int, int] = (0, 0, 0, 0) # x, y, w, h
        self.valid_bounds: bool = self.parse_bounds(self.bounds_str)
        
        # Fingerprint for re-selection persistence
        self.fingerprint: str = self._generate_fingerprint()

    def parse_bounds(self, bounds_str: str) -> bool:
        """
        Parses the "[x1,y1][x2,y2]" string into a tuple (x, y, w, h).

        Args:
            bounds_str (str): The bounds string from ADB.

        Returns:
            bool: True if bounds are valid (width > 0 and height > 0), False otherwise.
        """
        try:
            matches = re.findall(r'\[([-]?\d+),([-]?\d+)\]', bounds_str)
            if len(matches) == 2:
                x1, y1 = map(int, matches[0])
                x2, y2 = map(int, matches[1])
                w, h = x2 - x1, y2 - y1
                self.rect = (x1, y1, w, h)
                return w > 0 and h > 0
        except Exception: 
            pass
        return False

    def _generate_fingerprint(self) -> str:
        """
        Generates a unique MD5 hash based on the node's immutable properties.
        Used to restore selection when the tree is reloaded.
        """
        sig = f"{self.class_name}|{self.resource_id}|{self.text}|{self.content_desc}|{self.index}|{self.bounds_str}"
        return hashlib.md5(sig.encode()).hexdigest()

    def add_child(self, child_node: 'UiNode') -> None:
        """
        Adds a child node to this node's children list.

        Args:
            child_node (UiNode): The child node to add.
        """
        self.children.append(child_node)

class UixParser:
    """
    Static Parser engine for UIX files.
    """

    @staticmethod
    def _sanitize_xml(raw: str) -> str:
        """
        Attempts to trim junk before/after the XML root and recover valid hierarchy blocks.
        """
        if not raw:
            return raw

        text = raw.strip()

        # Remove leading garbage before first '<'
        first_tag = text.find("<")
        if first_tag > 0:
            text = text[first_tag:]

        # Prefer a complete <hierarchy> block if present
        start = text.find("<hierarchy")
        end = text.rfind("</hierarchy>")
        if start != -1 and end != -1 and end > start:
            return text[start:end + len("</hierarchy>")]

        # Fallback: wrap a <node> root in <hierarchy>
        start = text.find("<node")
        end = text.rfind("</node>")
        if start != -1 and end != -1 and end > start:
            return f"<hierarchy>{text[start:end + len('</node>')]}</hierarchy>"

        return text

    @staticmethod
    def parse(source: Union[str, bytes]) -> Tuple[Optional[UiNode], bool]:
        """
        Parses an XML source (string, bytes, or file path) into a UiNode tree.

        Args:
            source (Union[str, bytes]): XML content string, bytes, or file path.

        Returns:
            Tuple[Optional[UiNode], bool]: 
                - Root node of the parsed tree (or None on failure).
                - A boolean flag indicating if parsing failed or resulted in zero valid bounds.
        """
        try:
            root_element: ET.Element
            
            # Detect if source is content or path
            if isinstance(source, bytes) or (isinstance(source, str) and source.strip().startswith("<")):
                if isinstance(source, bytes): 
                    source = source.decode('utf-8', errors='replace')
                # Remove XML declaration if present to avoid encoding issues
                source = re.sub(r'<\?xml.*?\?>', '', source)
                source = UixParser._sanitize_xml(source)
                root_element = ET.fromstring(source)
            else:
                # Assume it's a file path
                tree = ET.parse(source)
                root_element = tree.getroot()
            
            # Recursive Builder
            valid_count: int = 0
            total_nodes: int = 0

            def build(element: ET.Element, parent: Optional[UiNode] = None) -> UiNode:
                nonlocal valid_count, total_nodes
                node = UiNode(element, parent)
                total_nodes += 1
                if node.valid_bounds: 
                    valid_count += 1
                
                for child in element:
                    node.add_child(build(child, node))
                return node

            # Handle basic wrapper tags like <hierarchy>
            start_element = root_element
            if root_element.tag == 'hierarchy' and len(root_element) > 0:
                start_element = root_element[0]
            
            root_node = build(start_element)
            
            # Heuristic: If we parsed nodes but ALL have 0 bounds, something is presumably wrong 
            # (or it's a non-visual dump)
            is_error = (valid_count == 0) and (total_nodes > 0)
            return root_node, is_error

        except Exception as e:
            print(f"XML Parse Error: {e}")
            return None, True
