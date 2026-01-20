from __future__ import annotations


def build_vision_prompt(page_index: int, width: float, height: float) -> str:
    """
    Builds the production-ready prompt for vision-based form parsing.
    """
    return (
        "You MUST extract fields ONLY from what is visible in the provided image.\n"
        "Do NOT invent fields. Do NOT translate labels into English unless the label is printed in English.\n\n"
        "TASK:\n"
        "Detect every human-writable input area in the form image and output a JSON array of fields.\n\n"
        "IMPORTANT RULES (anti-hallucination):\n"
        "- If you cannot see a field, do not include it.\n"
        '- Use the exact printed label text near the field (Japanese allowed). If no label exists, set label to "" and explain via section+notes.\n'
        '- Never output generic fields like "email", "employment_status", etc. unless those exact labels exist in the image.\n'
        "- Coordinates MUST correspond to the actual writable region (inside the box/underline).\n\n"
        "OUTPUT FORMAT:\n"
        "Return JSON ONLY (no markdown, no commentary). Output must be an array.\n\n"
        "Each item must be:\n"
        "{\n"
        '  "id": "stable_snake_case_id",\n'
        '  "label": "EXACT label text as printed near the field (keep original language)",\n'
        f'  "page_index": {page_index},\n'
        '  "x": <number>, "y": <number>, "w": <number>, "h": <number>,\n'
        '  "kind": "text" | "number" | "date" | "checkbox" | "radio" | "signature" | "stamp",\n'
        '  "section": "<short logical group name derived from nearby headings>",\n'
        '  "notes": "<optional: only if needed, e.g., \'label missing\', \'multiple boxes for year/month/day\'>"\n'
        "}\n\n"
        "COORDINATE SYSTEM:\n"
        "- Origin is top-left of the IMAGE (0,0).\n"
        f"- Use pixel coordinates relative to the given image width/height (width={width}, height={height}).\n"
        "- x,y = top-left of writable region; w,h = writable region size.\n\n"
        "EXHAUSTIVENESS REQUIREMENT:\n"
        "Perform TWO passes internally:\n"
        "Pass 1) Identify all sections/headings and all tables/rows that contain writable areas.\n"
        "Pass 2) Enumerate every writable area (including repeated rows) and output one JSON item per writable area.\n"
        "- For tables: expand row-by-row and cell-by-cell if each cell is writable.\n"
        "- For date fields like 年/月/日: output separate items per box (or per sub-box) if they are distinct.\n"
        "- For checkboxes/radios: output one item per checkbox/radio.\n\n"
        f"IMAGE CONTEXT:\n"
        f"- page_index: {page_index}\n"
        f"- image_width_px: {width}\n"
        f"- image_height_px: {height}\n\n"
        "QUALITY CHECK BEFORE FINAL OUTPUT:\n"
        "- Ensure the output contains ONLY fields that exist in the image.\n"
        "- Ensure no duplicates (same label+same region).\n"
        "- Ensure x,y,w,h are within the image bounds.\n"
        "Return the final JSON array now."
    )


def build_enrichment_prompt(page_index: int, width: float, height: float, fields_json: str) -> str:
    """
    Builds a concise prompt for enriching AcroForm fields with visual context.
    Optimized for speed while maintaining accuracy.
    """
    return (
        f"Analyze this Japanese form (Page {page_index}, {width}x{height}) and enrich the field labels.\\n\\n"
        
        f"INPUT FIELDS:\\n{fields_json}\\n\\n"
        
        "TASK: For each field, look at its coordinates in the image and identify:\\n"
        "1. The exact Japanese label printed near that position\\n"
        "2. Logical section (e.g., '納税者情報', '配偶者情報', '日付情報')\\n"
        "3. Brief note if helpful (e.g., '年', '月', '日')\\n\\n"
        
        "RULES:\\n"
        "- Keep original 'id' unchanged\\n"
        "- Extract exact text from image (preserve Japanese)\\n"
        "- Only enrich provided fields, don't add new ones\\n"
        "- Use consistent section names for similar fields\\n\\n"
        
        "EXAMPLES:\\n"
        '{\"id\":\"Text1\",\"label\":\"氏名\",\"section\":\"納税者情報\",\"notes\":\"\"}\\n'
        '{\"id\":\"Text2\",\"label\":\"フリガナ\",\"section\":\"納税者情報\",\"notes\":\"\"}\\n'
        '{\"id\":\"Text6\",\"label\":\"年\",\"section\":\"日付情報\",\"notes\":\"年\"}\\n\\n'
        
        "Return ONLY a valid JSON array with all fields enriched."
    )

