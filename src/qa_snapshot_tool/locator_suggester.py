from typing import List, Dict


class LocatorSuggester:
    @staticmethod
    def generate_locators(node) -> List[Dict[str, str]]:
        """
        Returns exactly three suggestions:
        A) Robust attribute-based XPath (scoped)
        B) Short XPath under chosen anchor
        C) Non-XPath selector heuristic
        """
        robust_xpath = LocatorSuggester._robust_scoped_xpath(node)
        short_xpath = LocatorSuggester._short_scoped_xpath(node)
        non_xpath = LocatorSuggester._non_xpath_heuristic(node)

        return [
            {
                "type": "A) Robust XPath (Scoped)",
                "strategy": "xpath",
                "value": robust_xpath,
                "xpath": robust_xpath,
            },
            {
                "type": "B) Short XPath (Anchor)",
                "strategy": "xpath",
                "value": short_xpath,
                "xpath": short_xpath,
            },
            {
                "type": "C) Non-XPath Heuristic",
                "strategy": "selector",
                "value": non_xpath,
                "xpath": "",
            },
        ]

    @staticmethod
    def _robust_scoped_xpath(node) -> str:
        anchor = LocatorSuggester._find_anchor(node)
        target_pred = LocatorSuggester._target_predicate(node, robust=True)
        if anchor:
            return f"{anchor}//{target_pred}"
        return f"//{target_pred}"

    @staticmethod
    def _short_scoped_xpath(node) -> str:
        anchor = LocatorSuggester._find_anchor(node)
        segment = LocatorSuggester._segment_minimal(node)
        if anchor:
            return f"{anchor}//{segment}"
        return f"//{segment}"

    @staticmethod
    def _non_xpath_heuristic(node) -> str:
        parts = []
        if node.resource_id:
            parts.append(f"resource-id={node.resource_id}")
        if node.text:
            parts.append(f"text={node.text}")
        if node.content_desc:
            parts.append(f"content-desc={node.content_desc}")
        if node.class_name:
            parts.append(f"class={node.class_name}")

        if not parts:
            return "class=UNKNOWN; index=0"

        # Add sibling class index as disambiguator
        parts.append(f"classIndex={node.class_index()}")
        return "; ".join(parts)

    @staticmethod
    def _find_anchor(node) -> str:
        for ancestor in node.iter_ancestors():
            if ancestor.resource_id:
                return f"//*[@resource-id={LocatorSuggester._xpath_literal(ancestor.resource_id)}]"
            if ancestor.content_desc:
                return f"//*[@content-desc={LocatorSuggester._xpath_literal(ancestor.content_desc)}]"
            if ancestor.text and len(ancestor.text) <= 40:
                return f"//*[@text={LocatorSuggester._xpath_literal(ancestor.text)}]"
        return ""

    @staticmethod
    def _target_predicate(node, robust: bool = True) -> str:
        predicates = []

        if node.resource_id:
            predicates.append(f"@resource-id={LocatorSuggester._xpath_literal(node.resource_id)}")
        if node.content_desc:
            predicates.append(f"@content-desc={LocatorSuggester._xpath_literal(node.content_desc)}")
        if node.text:
            predicates.append(f"@text={LocatorSuggester._xpath_literal(node.text)}")
        if node.class_name:
            predicates.append(f"@class={LocatorSuggester._xpath_literal(node.class_name)}")

        if not predicates:
            return "*"

        if robust and len(predicates) >= 2:
            return f"*[{ ' and '.join(predicates) }]"

        return f"*[{predicates[0]}]"

    @staticmethod
    def _segment_minimal(node) -> str:
        if node.resource_id:
            return f"*[@resource-id={LocatorSuggester._xpath_literal(node.resource_id)}]"
        if node.text and node.class_name:
            return f"*[@class={LocatorSuggester._xpath_literal(node.class_name)} and @text={LocatorSuggester._xpath_literal(node.text)}]"
        if node.content_desc:
            return f"*[@content-desc={LocatorSuggester._xpath_literal(node.content_desc)}]"
        if node.class_name:
            return f"*[@class={LocatorSuggester._xpath_literal(node.class_name)}][{node.class_index()}]"
        return "*"

    @staticmethod
    def _xpath_literal(value: str) -> str:
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        joined = ", \"'\", ".join([f"'{p}'" for p in parts])
        return f"concat({joined})"