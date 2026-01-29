import xml.etree.ElementTree as ET
import re
from typing import Optional, List, Dict


class UiNode:
    def __init__(self, element: ET.Element, parent: Optional["UiNode"] = None, index_in_parent: int = 0):
        self.element = element
        self.parent = parent
        self.children: List[UiNode] = []
        self.index_in_parent = index_in_parent
        self.depth = 0 if not parent else parent.depth + 1

        # Raw attributes
        self.attributes: Dict[str, str] = dict(element.attrib) if element is not None else {}

        # Common attributes
        self.text = element.get("text", "")
        self.resource_id = element.get("resource-id", "")
        self.class_name = element.get("class", "")
        self.package = element.get("package", "")
        self.content_desc = element.get("content-desc", "")
        self.checkable = element.get("checkable", "false") == "true"
        self.checked = element.get("checked", "false") == "true"
        self.clickable = element.get("clickable", "false") == "true"
        self.enabled = element.get("enabled", "false") == "true"
        self.focusable = element.get("focusable", "false") == "true"
        self.focused = element.get("focused", "false") == "true"
        self.scrollable = element.get("scrollable", "false") == "true"
        self.long_clickable = element.get("long-clickable", "false") == "true"
        self.password = element.get("password", "false") == "true"
        self.selected = element.get("selected", "false") == "true"

        # Parse bounds: "[x1,y1][x2,y2]"
        self.rect = (0, 0, 0, 0)  # x, y, w, h
        self.bounds_raw = element.get("bounds", "[0,0][0,0]")
        self.parse_bounds(self.bounds_raw)

    def parse_bounds(self, bounds_str: str) -> None:
        try:
            matches = re.findall(r"\[(\d+),(\d+)\]", bounds_str or "")
            if len(matches) == 2:
                x1, y1 = map(int, matches[0])
                x2, y2 = map(int, matches[1])
                self.rect = (x1, y1, max(0, x2 - x1), max(0, y2 - y1))
        except Exception:
            self.rect = (0, 0, 0, 0)

    def add_child(self, child_node: "UiNode") -> None:
        self.children.append(child_node)

    def iter_ancestors(self):
        current = self.parent
        while current:
            yield current
            current = current.parent

    def siblings(self) -> List["UiNode"]:
        if not self.parent:
            return []
        return self.parent.children

    def same_class_siblings(self) -> List["UiNode"]:
        return [s for s in self.siblings() if s.class_name == self.class_name]

    def class_index(self) -> int:
        same = self.same_class_siblings()
        for i, s in enumerate(same, start=1):
            if s is self:
                return i
        return 1

class UixParser:
    @staticmethod
    def parse(file_path):
        try:
            tree = ET.parse(file_path)
            root_element = tree.getroot()
            
            # Helper to recursively build tree
            def build_tree(element, parent=None, index_in_parent=0):
                node = UiNode(element, parent, index_in_parent=index_in_parent)
                for idx, child_element in enumerate(element):
                    child_node = build_tree(child_element, node, index_in_parent=idx)
                    node.add_child(child_node)
                return node

            # The root of uiautomator dump usually wraps the hierarchy
            # Sometimes the first node is "hierarchy" which contains the window
            if root_element.tag == "hierarchy":
                # Grab the first real view group if available
                if len(root_element) > 0:
                    return build_tree(root_element[0], None, 0)
            
            return build_tree(root_element, None, 0)

        except Exception as e:
            print(f"Error parsing UIX: {e}")
            return None