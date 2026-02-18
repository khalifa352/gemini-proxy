import os
import json
import logging
import re
import time
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SYSTEM CONFIGURATION & LOGGING
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [V16-GEO] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ======================================================
# 🤖 GENAI CLIENT
# ======================================================
client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
except ImportError:
    logger.warning("Google GenAI SDK not found. AI features disabled.")
except Exception as e:
    logger.error(f"Failed to initialize GenAI Client: {e}")

# ======================================================
# 🧠 REGEX ENGINE
# ======================================================

# Improved JSON Extraction: Looks for code blocks first, then falls back to curly braces
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
SVG_EXTRACT_RE = re.compile(r"(?s)<svg[^>]*>.*?</svg>")
ARABIC_EXTENDED_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")

# ======================================================
# 📐 ALMONJEZ CONSTITUTION & GEO PROTOCOL
# ======================================================
ALMONJEZ_CONSTITUTION = {
    "1_Hierarchy": "Headlines MUST be 3x body size using Modular Scale 1.25.",
    "2_Contrast": "Strict Opacity Tiers: BG=0.12, Shape=0.45, Text=1.0.",
    "3_Arabic_BiDi": "FORCE 'direction: rtl' on Arabic text. Flip text-anchor: start -> end.",
    "4_Geo_Safety": "Keep content within Safe Zone (5mm margin). Round coordinates to 2 decimals.",
    "5_Brand": "Brand Name is SACRED. Exact spelling match required."
}

GEO_PROTOCOL = {
    "opacity_tiers": {"bg": 0.12, "mid": 0.45, "focus": 1.0},
    "precision": 2,
    "safe_margin_pct": 0.05,
    "bleed_mm": 3,
    "safe_zone_mm": 5,
    "modular_scale": 1.25,
    "typography_sizes": {"body": 16, "subheading": 20, "h2": 25, "h1": 31, "display": 39}
}

# ======================================================
# 🛡️ SANITIZATION MIDDLEWARE
# ======================================================

def sanitize_json_payload(raw_text):
    """
    Robustly extracts the first valid JSON object from the raw text.
    Fixes 'Extra data' errors by not reading beyond the first closing brace.
    """
    if not raw_text: return None

    # 1. Try extracting from markdown code blocks first
    match = JSON_BLOCK_RE.search(raw_text)
    if match:
        json_str = match.group(1)
    else:
        # 2. Fallback: Find first '{'
        start = raw_text.find('{')
        if start == -1: return None
        
        # 3. Smart extraction: Count braces to find the matching '}'
        # This prevents including extra text/SVG that comes after the JSON
        balance = 0
        end = -1
        for i, char in enumerate(raw_text[start:], start):
            if char == '{':
                balance += 1
            elif char == '}':
                balance -= 1
                if balance == 0:
                    end = i + 1
                    break
        
        if end == -1: return None # Unclosed JSON
        json_str = raw_text[start:end]

    # 4. Clean up common errors
    json_str = re.sub(r"//.*", "", json_str) # Remove comments
    json_str = re.sub(r",\s*}", "}", json_str) # Trailing commas
    json_str = re.sub(r",\s*]", "]", json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error: {e}")
        return None

# ======================================================
# 🔧 ENGINEERING UTILS
# ======================================================

def is_arabic_advanced(text):
    return bool(ARABIC_EXTENDED_RE.search(text))

def apply_opacity_tier(element_type):
    tiers = GEO_PROTOCOL["opacity_tiers"]
    t = element_type.lower()
    if t in ["background", "bg", "texture"]: return tiers["bg"]
    if t in ["shape", "mid", "depth"]: return tiers["mid"]
    if t in ["text", "focus", "content"]: return tiers["focus"]
    return tiers["focus"]

def enforce_safe_zone(x, y, width, height, viewbox_width=1080, viewbox_height=1080):
    safe_margin = GEO_PROTOCOL["safe_margin_pct"] * min(viewbox_width, viewbox_height)
    bleed = 18 
    
    # Allow bleed for backgrounds
    if x < 0: x -= bleed
    if y < 0: y -= bleed
    if x + width > viewbox_width: width += bleed
    if y + height > viewbox_height: height += bleed
    
    # Constrain content
    x = max(x, safe_margin)
    y = max(y, safe_margin)
    width = min(width, viewbox_width - 2 * safe_margin)
    height = min(height, viewbox_height - 2 * safe_margin)
    
    return x, y, width, height

def optimize_path_data(d):
    # Round decimals
    d = re.sub(r"(\d+\.\d{3,})", lambda m: f"{float(m.group(1)):.2f}", d)
    # Close paths if they start with M and look closed
    if d.strip() and d.strip()[-1].upper() != 'Z' and d.startswith('M'):
        coords = re.findall(r"[-+]?\d*\.?\d+", d)
        if len(coords) >= 4:
            d += 'Z'
    return d

def enforce_geo_protocol(svg_code, viewbox_width=1080, viewbox_height=1080):
    if not svg_code: return svg_code
    
    # 1. Rounding
    svg_code = re.sub(r"(\d+\.\d{3,})", lambda m: f"{float(m.group(1)):.2f}", svg_code)
    
    # 2. Optimize paths
    svg_code = re.sub(r'd="([^"]+)"', lambda m: f'd="{optimize_path_data(m.group(1))}"', svg_code)
    
    # 3. Apply opacity tiers
    def adjust_opacity(match):
        tag = match.group(0)
        if "opacity" not in tag:
            element_type = "bg" if "fill" in tag and "stroke" not in tag else "mid" if "path" in tag else "focus"
            opacity = apply_opacity_tier(element_type)
            tag = tag.replace(">", f' opacity="{opacity}">', 1)
        return tag
    svg_code = re.sub(r"<(rect|circle|ellipse|path|text|tspan)[^>]*>", adjust_opacity, svg_code)
    
    # 4. Enforce safe zones
    def adjust_coords(match):
        tag = match.group(0)
        attrs = re.findall(r'(\w+)="([^"]+)"', tag)
        attr_dict = dict(attrs)
        
        if 'x' in attr_dict and 'y' in attr_dict and 'width' in attr_dict and 'height' in attr_dict:
            try:
                x, y, w, h = map(float, [attr_dict['x'], attr_dict['y'], attr_dict['width'], attr_dict['height']])
                x, y, w, h = enforce_safe_zone(x, y, w, h, viewbox_width, viewbox_height)
                for key, val in {'x': x, 'y': y, 'width': w, 'height': h}.items():
                    tag = re.sub(f'{key}="[^"]+"', f'{key}="{val:.2f}"', tag)
            except: pass
        return tag
    svg_code = re.sub(r"<(rect|image|text)[^>]*>", adjust_coords, svg_code)
    
    return svg_code

def inject_bidi_attributes(svg_code):
    if not svg_code: return svg_code
    def replace_text_tag(match):
        tag_content = match.group(0)
        if is_arabic_advanced(tag_content):
            if "direction" not in tag_content:
                tag_content = tag_content.replace("<text", '<text direction="rtl" unicode-bidi="embed"')
            
            if 'text-anchor="start"' in tag_content:
                tag_content = tag_content.replace('text-anchor="start"', 'text-anchor="end"')
            elif 'text-anchor="end"' in tag_content:
                tag_content = tag_content.replace('text-anchor="end"', 'text-anchor="start"')
                
            if "font-family" not in tag_content:
                tag_content = tag_content.replace("<text", '<text font-family="Arial, sans-serif"')
        return tag_content
    svg_code = re.sub(r"<text[^>]*>.*?</text>", replace_text_tag, svg_code, flags=re.DOTALL)
    return svg_code

# ======================================================
# 👮‍♂️ VALIDATORS
# ======================================================

def validate_plan_content(plan):
    if not isinstance(plan, dict): return False, "Invalid JSON Object."
    contract = plan.get("design_contract")
    if not isinstance(contract, dict): return False, "Missing 'design_contract'."
    if str(contract.get("contrast_verified", "")).upper() != "YES":
        return False, "Contrast Verification Failed."
    if len(contract.get("main_rules_applied", [])) < 3:
        return False, "Constitution Violation."
    return True, "Valid"

def validate_svg_quality(svg_code):
    if not svg_code or "<svg" not in svg_code: return False, "No valid SVG tag found."
    
    # BiDi Check
    text_content = re.sub(r"<[^>]+>", "", svg_code)
    if is_arabic_advanced(text_content):
        if "direction" not in svg_code.lower() and "rtl" not in svg_code.lower():
             pass 

    # Stroke Check
    strokes = re.findall(r'stroke-width=["\']([\d\.]+)["\']', svg_code)
    if any(float(w) > 2.0 for w in strokes if w):
        return False, "Geo Protocol Violation: Stroke too thick."

    return True, "Quality OK"

# ======================================================
# 🚀 APP LOGIC
# ======================================================

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Backend Unavailable"}), 500

    try:
        data = request.json or {}
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        
        width = int(data.get('width', 1080))
        height = int(data.get('height', 1080))
        
        indexed_rules = [f"{k}: {v}" for k,v in ALMONJEZ_CONSTITUTION.items()]
        
        # Define Template
        plan_template = f"""
REQUIRED JSON PLAN FORMAT:
```json
{{
  "design_contract": {{
    "arabic_position": "top_right",
    "contrast_verified": "YES",
    "layout_variant": "hero",
    "opacity_tiers_used": ["0.12", "0.45", "1.0"],
    "main_rules_applied": ["1_Hierarchy", "3_Arabic_BiDi", "4_Geo_Safety"]
  }}
}}
"""
# Define System Instructions
       sys_instructions = f"""
    ROLE: Almonjez V16 Engineering Architect.

    --- CONSTITUTION (STRICT) ---
    {json.dumps(indexed_rules, indent=2)}
    
    --- GEO PROTOCOL ---
    1. Opacity Tiers: Background=0.12, Shapes=0.45, Text=1.0. NO exceptions.
    2. Precision: All coordinates must be rounded to 2 decimals.
    3. Safe Zone: Keep important content 50px inside borders.
    
    --- ARABIC BIDI RULES ---
    1. IF Arabic text detected: Add `direction="rtl"` to parent tag.
    2. Set `text-anchor="end"` for Arabic headers (align right).
    
    --- OUTPUT PROTOCOL ---
    1. Generate the JSON Plan (Strict Format).
    2. Generate the SVG Code (Clean, Valid XML).
    {plan_template}
    """

    max_attempts = 2
    final_svg = None
    used_model = "unknown"
    extracted_plan = None
    fail_reason = ""
    
    # ✅ UPDATED: Use available stable models
    models = ["gemini-2.0-flash", "gemini-1.5-pro"]
    
    for attempt in range(max_attempts):
        model = models[0] if attempt == 0 else models[-1]
        try:
            current_sys = sys_instructions
            if attempt > 0:
                current_sys += f"\n\nPREVIOUS FAILURE: {fail_reason}. COMPLY WITH GEO PROTOCOL."

            response = client.models.generate_content(
                model=model,
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=current_sys, 
                    temperature=0.6 if attempt==0 else 0.4
                )
            )
            
            raw = response.text or ""
            
            # 1. Sanitize & Extract Plan (Robust)
            plan = sanitize_json_payload(raw)
            
            # 2. Validate Plan
            is_plan_ok, p_reason = validate_plan_content(plan)
            if not is_plan_ok:
                fail_reason = f"Plan Error: {p_reason}"
                continue

            # 3. Extract SVG
            svg_match = SVG_EXTRACT_RE.search(raw)
            if not svg_match:
                fail_reason = "No valid SVG block found."
                continue
            svg_code = svg_match.group(0)

            # 4. Validate SVG Quality
            is_svg_ok, s_reason = validate_svg_quality(svg_code)
            if not is_svg_ok:
                fail_reason = f"SVG Quality Error: {s_reason}"
                continue

            final_svg = svg_code
            extracted_plan = plan
            used_model = model
            break
            
        except Exception as e:
            fail_reason = str(e)
            time.sleep(1)

    if not final_svg:
         return jsonify({"error": "V16 Compliance Failure", "details": fail_reason}), 500

    # Post-Processing
    final_svg = enforce_geo_protocol(final_svg, width, height)
    final_svg = inject_bidi_attributes(final_svg)
    
    if 'xmlns=' not in final_svg: 
        final_svg = final_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    
    return jsonify({
        "response": final_svg,
        "meta": {"model": used_model, "plan": extracted_plan}
    })

except Exception as e:
    logger.critical(f"Fatal System Error: {e}")
    return jsonify({"error": str(e)}), 500
if name == 'main':
port = int(os.environ.get('PORT', 10000))
app.run(host='0.0.0.0', port=port)
