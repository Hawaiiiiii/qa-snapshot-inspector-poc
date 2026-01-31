class LocatorUtils:
    @staticmethod
    def escape_xpath_string(text):
        if "'" in text:
            parts = text.split("'")
            args = [f"'{p}'" for p in parts]
            concat = ", \"'\", ".join(args)
            return f"concat({concat})"
        return f"'{text}'"

class LocatorSuggester:
    @staticmethod
    def generate_locators(node, root_node):
        suggestions = []

        # 1. SCOPED LOCATOR (The "Leandro" Requirement)
        # Find a stable anchor (ID) up the tree, then find the target relative to it.
        scoped = LocatorSuggester._generate_scoped_locator(node)
        if scoped: suggestions.append(scoped)

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
    def _generate_scoped_locator(node):
        # 1. Find Anchor
        anchor = None
        curr = node.parent
        bad_ids = ["android:id/content", "android:id/body", "id/container"] # Generic IDs we hate
        
        while curr:
            if curr.resource_id:
                is_bad = any(b in curr.resource_id for b in bad_ids)
                if not is_bad:
                    anchor = curr
                    break
            curr = curr.parent
            
        if not anchor: return None

        # 2. Build Relative Path
        anchor_xpath = f"//*[@resource-id='{anchor.resource_id}']"
        
        # Target Logic
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