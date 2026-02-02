"""
Robotic Command Interpreter for SO101 Jenga Arm

Converts natural language to structured JSON commands for a robotic arm
that sorts Jenga blocks using a RealSense depth camera.

Actions:
- PICK: Retrieve specific block(s)
- SORT: Organize blocks by attribute
- DECLINE: Request outside capabilities
"""

import re
import json
from typing import Optional, Dict, Any

# ============================================================
# VALID VALUES
# ============================================================
VALID_COLORS = {"red", "blue", "green", "yellow", "pink", "wood", "any"}
VALID_ACTIONS = {"PICK", "PLACE", "DROP", "DECLINE"}

# Color synonyms mapping
COLOR_MAP = {
    # Red variants
    "red": "red", "crimson": "red", "scarlet": "red", "ruby": "red", "maroon": "red",
    # Blue variants
    "blue": "blue", "azure": "blue", "navy": "blue", "cyan": "blue", "teal": "blue",
    # Green variants
    "green": "green", "lime": "green", "emerald": "green", "olive": "green", "mint": "green",
    # Yellow variants
    "yellow": "yellow", "gold": "yellow", "amber": "yellow", "lemon": "yellow",
    # Pink variants
    "pink": "pink", "magenta": "pink", "rose": "pink", "fuchsia": "pink",
    # Wood/natural
    "wood": "wood", "brown": "wood", "tan": "wood", "beige": "wood", "natural": "wood",
}

# Action keyword mapping
PICK_KEYWORDS = {"grab", "get", "bring", "lift", "pick", "take", "fetch", "retrieve", "collect"}
PLACE_KEYWORDS = {"place", "put", "set", "position", "drop off", "lay down", "deposit"}
DROP_KEYWORDS = {"drop", "release", "let go", "put down", "set down"}
DECLINE_KEYWORDS = {"dance", "wave", "stack", "build", "throw", "jump", "spin"}

# Spatial context mapping
SPATIAL_MAP = {
    # Top/nearest
    "top": "top", "topmost": "top", "upper": "top", "highest": "top",
    "nearest": "nearest", "closest": "nearest", "close": "nearest",
    # Bottom
    "bottom": "bottom", "lowest": "bottom", "base": "bottom",
    # Left/Right
    "left": "left", "leftmost": "left",
    "right": "right", "rightmost": "right",
    # Center
    "center": "center", "middle": "center", "central": "center",
    # First/Last
    "first": "first", "last": "last",
}


class JengaCommandInterpreter:
    """
    Interprets natural language commands for Jenga robot.
    Outputs structured JSON.
    """
    
    def interpret(self, user_input: str) -> Dict[str, Any]:
        """
        Convert natural language to JSON command.
        
        Returns dict with:
        - action_type: PICK | SORT | DECLINE
        - parameters: {target_color, quantity, sort_criteria}
        - reasoning: Brief explanation
        """
        text = user_input.lower().strip()
        
        # Determine action type
        action_type = self._detect_action(text)
        
        # Build response based on action
        if action_type == "DECLINE":
            return {
                "action_type": "DECLINE",
                "parameters": {
                    "target_color": None,
                    "sort_criteria": None
                },
                "reasoning": "Request outside robot capabilities."
            }
        
        elif action_type == "PLACE":
            return {
                "action_type": "PLACE",
                "parameters": {
                },
                "reasoning": f"Organize all blocks by "
            }
        
        elif action_type == "DROP":
            return {
                "action_type": "DROP",
                "parameters": {
                },
                "reasoning": f"Organize all blocks by "
            }
        
        else:  # PICK
            color = self._detect_color(text)
            # quantity = self._detect_quantity(text)
            spatial = self._detect_spatial(text)
            
            # Build reasoning
            parts = []
            if color and color != "any":
                parts.append(color)
            if spatial:
                parts.append(f"({spatial})")
            parts.append("block(s).")
            reasoning = " ".join(parts)
            
            return {
                "action_type": "PICK",
                "parameters": {
                    "target_color": color,

                    "spatial_context": spatial,
                    "sort_criteria": None
                },
                "reasoning": reasoning
            }
    
    def _detect_action(self, text: str) -> str:
        """Detect action type from text."""
        words = set(text.split())
        
        # Check for decline keywords first
        if words & DECLINE_KEYWORDS:
            return "DECLINE"
        
        # Check for sort keywords
        if words :
            return "SORT"
        
        # Check for pick keywords
        if words & PICK_KEYWORDS:
            return "PICK"
        
        # Default to PICK for ambiguous requests about blocks
        if any(w in text for w in ["block", "piece", "jenga"]):
            return "PICK"
        
        # If nothing matches, decline
        return "DECLINE"
    
    def _detect_color(self, text: str) -> Optional[str]:
        """Extract color from text."""
        words = text.split()
        
        for word in words:
            # Clean punctuation
            clean = re.sub(r'[^\w]', '', word)
            if clean in COLOR_MAP:
                return COLOR_MAP[clean]
        
        # Check for "any" color
        if "any" in text or "random" in text:
            return "any"
        
        return None
    
    # def _detect_quantity(self, text: str) -> int:
    #     """Extract quantity from text."""
    #     text_lower = text.lower()
        
    #     # Check for "all"
    #     if any(w in text_lower for w in ["all", "every", "everything"]):
    #         return -1
        
    #     # Look for numbers
    #     numbers = re.findall(r'\b(\d+)\b', text)
    #     if numbers:
    #         return int(numbers[0])
        
    #     # Word numbers
    #     word_nums = {
    #         "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    #         "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
    #     }
    #     for word, num in word_nums.items():
    #         if word in text_lower:
    #             return num
        
    #     # Default to 1
    #     return 1
    
    # def _detect_sort_criteria(self, text: str) -> str:
    #     """Detect sorting criteria."""
    #     if "color" in text or "colour" in text:
    #         return "color"
    #     if "random" in text:
    #         return "random"
    #     # Default to color
    #     return "color"
    
    def _detect_spatial(self, text: str) -> Optional[str]:
        """Detect spatial context from text."""
        words = text.split()
        
        for word in words:
            clean = re.sub(r'[^\w]', '', word)
            if clean in SPATIAL_MAP:
                return SPATIAL_MAP[clean]
        
        return None
    
    def get_json(self, user_input: str) -> str:
        """Get raw JSON string output."""
        result = self.interpret(user_input)
        return json.dumps(result)


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    interpreter = JengaCommandInterpreter()
    
    test_inputs = [
        "grab the red block",
        "pick up the blue piece",
        "get me 3 green blocks",
        "bring all the yellow ones",
        "organize the blocks by color",
        "sort everything",
        "clean up the table",
        "get the emerald block",  # Should map to green
        "dance around",  # Should DECLINE
        "stack the blocks",  # Should DECLINE
        "pick any block",
        "get two pink blocks",
        # Spatial context tests
        "grab the top block",
        "get the nearest red piece",
        "pick the bottom yellow block",
        "bring the leftmost green one",
    ]
    
    print("=" * 60)
    print("Jenga Command Interpreter Test")
    print("=" * 60)
    
    for inp in test_inputs:
        result = interpreter.interpret(inp)
        print(f"\nInput: \"{inp}\"")
        print(json.dumps(result, indent=2))
