"""
Locator Suggester Module.

Generates robust XPath and ID-based locators for test automation (Appium/Selenium)
based on the properties of a selected `UiNode`. It prioritizes "scoped" locators
that rely on stable parent anchors.
"""

from typing import List, Dict, Optional, Any, Union
from .uix_parser import UiNode

class LocatorUtils:
    """Utility functions for string escaping in XPath."""
    
    @staticmethod
    def escape_xpath_string(text: str) -> str:
        """
        Escapes single quotes in text for use in XPath expressions.
        Example: "User's" -> concat("User", "'", "s")
        """
        if "'" in text:
            parts = text.split("'")
            # Wrap each part in single quotes
            args = [f"'{p}'" for p in parts]
            # Join with the escaped single quote
            concat = ", \"'\", ".join(args)
            return f"concat({concat})"
        return f"'{text}'"

class LocatorSuggester:
    """
    Engine for calculating the best automation selectors.
    """

    @staticmethod
    def generate_locators(node: UiNode, root_node: Optional[UiNode] = None) -> List[Dict[str, Union[str, int]]]:
        """
        Generates a list of possible locators for a specific node.

        Args:
            node (UiNode): The target node to find locators for.
            root_node (Optional[UiNode]): The root of the tree (unused currently but reserved for full-path logic).

        Returns:
            List[Dict[str, Union[str, int]]]: A list of dictionary objects containing:
                - 'type': Description of the strategy (e.g., "Direct ID")
                - 'xpath': The actual locator string.
                - 'score': A heuristic score (higher is better).
        """
        suggestions: List[Dict[str, Union[str, int]]] = []

        # 1. SCOPED LOCATOR (The "Leandro" Requirement)
        # Find a stable anchor (ID) up the tree, then find the target relative to it.
        scoped = LocatorSuggester._generate_scoped_locator(node)
        if scoped: 
            suggestions.append(scoped)

        # 2. DIRECT ID (Only if it's not generic)
        if node.resource_id and "id/content" not in node.resource_id:
            suggestions.append({
                "type": "Direct ID",
                "xpath": f"//*[@resource-id='{node.resource_id}']",
                "score": 10
            })

        # 3. TEXT MATCH (Specific Class)
        if node.text:
            safe_text = LocatorUtils.escape_xpath_string(node.text)
            suggestions.append({
                "type": "Text Match",
                "xpath": f"//{node.class_name}[@text={safe_text}]",
                "score": 5
            })

        # 4. CONTENT-DESC
        if node.content_desc:
            safe_desc = LocatorUtils.escape_xpath_string(node.content_desc)
            suggestions.append({
                "type": "Content-Desc",
                "xpath": f"//*[@content-desc={safe_desc}]",
                "score": 8
            })

        return suggestions

    @staticmethod
    def _generate_scoped_locator(node: UiNode) -> Optional[Dict[str, Union[str, int]]]:
        """
        Tries to find a parent with a stable resource-id (Anchor) and builds a relative xpath.
        """
        # 1. Find Anchor
        anchor: Optional[UiNode] = None
        curr = node.parent
        bad_ids = ["android:id/content", "android:id/body", "id/container"] # Generic IDs we hate
        
        while curr:
            if curr.resource_id:
                is_bad = any(b in curr.resource_id for b in bad_ids)
                if not is_bad:
                    anchor = curr
                    break
            curr = curr.parent
            
        if not anchor: 
            return None

        # 2. Build Relative Path
        anchor_xpath = f"//*[@resource-id='{anchor.resource_id}']"
        
        # Target Logic
        target_xpath = ""
        if node.text:
            safe_text = LocatorUtils.escape_xpath_string(node.text)
            target_xpath = f".//{node.class_name}[@text={safe_text}]"
        elif node.content_desc:
            safe_desc = LocatorUtils.escape_xpath_string(node.content_desc)
            target_xpath = f".//*[@content-desc={safe_desc}]"
        elif node.resource_id:
             target_xpath = f".//*[@resource-id='{node.resource_id}']"
        else:
            # Fallback to class (weak, but better than nothing inside a scope)
            target_xpath = f".//{node.class_name}"

        return {
            "type": "Scoped (Parent -> Child)",
            "xpath": f"{anchor_xpath}{target_xpath}",
            "score": 20 # Highest Priority
        }
