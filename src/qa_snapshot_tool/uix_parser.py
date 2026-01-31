import xml.etree.ElementTree as ET
import re
import hashlib

class UiNode:
    def __init__(self, element, parent=None):
        self.element = element
        self.parent = parent
        self.children = []
        
        # Strings
        self.text = element.get('text', '')
        self.resource_id = element.get('resource-id', '')
        self.class_name = element.get('class', '')
        self.package = element.get('package', '')
        self.content_desc = element.get('content-desc', '')
        self.index = element.get('index', '0')
        
        # Booleans (Crucial for validation)
        self.checkable = element.get('checkable', 'false') == 'true'
        self.checked = element.get('checked', 'false') == 'true'
        self.clickable = element.get('clickable', 'false') == 'true'
        self.enabled = element.get('enabled', 'false') == 'true'
        self.focusable = element.get('focusable', 'false') == 'true'
        self.focused = element.get('focused', 'false') == 'true'
        self.scrollable = element.get('scrollable', 'false') == 'true'
        self.long_clickable = element.get('long-clickable', 'false') == 'true'
        self.password = element.get('password', 'false') == 'true'
        self.selected = element.get('selected', 'false') == 'true'
        
        # NAF Logic
        self.naf = element.get('NAF', 'false') == 'true'
        if not self.text and not self.resource_id and not self.content_desc:
            self.naf = True

        # Bounds Parsing
        self.bounds_str = element.get('bounds', '[0,0][0,0]')
        self.rect = (0, 0, 0, 0)
        self.valid_bounds = self.parse_bounds(self.bounds_str)
        
        # Fingerprint for re-selection
        self.fingerprint = self._generate_fingerprint()

    def parse_bounds(self, bounds_str):
        try:
            matches = re.findall(r'\[([-]?\d+),([-]?\d+)\]', bounds_str)
            if len(matches) == 2:
                x1, y1 = map(int, matches[0])
                x2, y2 = map(int, matches[1])
                w, h = x2 - x1, y2 - y1
                self.rect = (x1, y1, w, h)
                return w > 0 and h > 0
        except: pass
        return False

    def _generate_fingerprint(self):
        # Unique signature to restore selection after refresh
        sig = f"{self.class_name}|{self.resource_id}|{self.text}|{self.content_desc}|{self.index}|{self.bounds_str}"
        return hashlib.md5(sig.encode()).hexdigest()

    def add_child(self, child_node):
        self.children.append(child_node)

class UixParser:
    @staticmethod
    def parse(source):
        try:
            if isinstance(source, bytes) or (isinstance(source, str) and source.strip().startswith("<")):
                if isinstance(source, bytes): source = source.decode('utf-8', errors='replace')
                root_element = ET.fromstring(source)
            else:
                tree = ET.parse(source)
                root_element = tree.getroot()
            
            valid_count = 0
            total_nodes = 0

            def build(element, parent=None):
                nonlocal valid_count, total_nodes
                node = UiNode(element, parent)
                total_nodes += 1
                if node.valid_bounds: valid_count += 1
                for child in element:
                    node.add_child(build(child, node))
                return node

            start = root_element
            if root_element.tag == 'hierarchy' and len(root_element) > 0:
                start = root_element[0]
            
            root_node = build(start)
            # Heuristic: If we parsed nodes but ALL have 0 bounds, something is wrong
            is_bounds_all_zero = (valid_count == 0) and (total_nodes > 0)
            return root_node, is_bounds_all_zero

        except Exception as e:
            print(f"XML Parse Error: {e}")
            return None, True