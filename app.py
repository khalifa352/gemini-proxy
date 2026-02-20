import os
import re
import json
import math
import time
import logging
import random
from typing import Any, Dict, Optional, Tuple, List
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ CONFIGURATION (ALMONJEZ V40 - DETERMINISTIC SVG)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_V40")

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_PATH = os.path.join(BASE_DIR, "recipes", "core")
LAYOUT_FILE = os.path.join(CORE_PATH, "layout_sets.json")

# ======================================================
# 🔌 GEMINI CLIENT
# ======================================================
client = None
types = None
try:
    from google import genai
    from google.genai import types as _types
    types = _types
    API_KEY = os.environ.get("GOOGLE_API_KEY")
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1beta"})
        logger.info("✅ Gemini Client Connected (v1beta)")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY Missing")
except Exception as e:
    logger.error(f"❌ Gemini init error: {e}")

# ======================================================
# 🧠 UTIL: SANITIZER (ROBUST JSON PARSER)
# ======================================================
class Sanitizer:
    @staticmethod
    def _strip_code_fences(text: str) -> str:
        if not text:
            return ""
        text = text.replace("```json", "").replace("```", "").strip()
        return text

    @staticmethod
    def parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract first valid JSON object from raw text.
        Repairs trailing commas.
        """
        try:
            raw_text = Sanitizer._strip_code_fences(raw_text or "")
            # Try direct parse first
            try:
                return json.loads(raw_text)
            except Exception:
                pass

            # Extract { ... } block
            m = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not m:
                return None

            js = m.group(0)
            js = re.sub(r",\s*([\]}])", r"\1", js)  # remove trailing commas
            return json.loads(js)
        except Exception as e:
            logger.error(f"Sanitizer.parse_json failed: {e}")
            return None

# ======================================================
# 🔤 UTIL: ARABIC DETECTION
# ======================================================
ARABIC_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)

def contains_arabic(s: str) -> bool:
    return bool(ARABIC_RE.search(s or ""))

# ======================================================
# 📏 TEXT FIT ENGINE (AUTO FONT SIZE + LINE ESTIMATION)
# ======================================================
class TextFit:
    @staticmethod
    def _sanitize_html(text: str) -> str:
        if text is None:
            return ""
        # Minimal HTML escaping to avoid breaking tags
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @staticmethod
    def estimate_lines(text: str, box_w: int, font_px: int, rtl: bool) -> int:
        """
        Approximate line count.
        Arabic tends to be slightly wider at same font size in many fonts.
        """
        if not text:
            return 1

        # Effective char width factor
        # (tuned heuristically for Cairo/Tajawal-ish)
        char_w = font_px * (0.56 if rtl else 0.52)

        # Some punctuation/latin mixes increase width unpredictably
        # We add a small penalty when mixing LTR content.
        mix_penalty = 1.10 if (rtl and re.search(r"[A-Za-z0-9]", text)) else 1.0

        capacity = max(1, int(box_w / (char_w * mix_penalty)))
        # rough word-wrap simulation
        words = re.split(r"\s+", text.strip())
        lines = 1
        cur = 0
        for w in words:
            if not w:
                continue
            needed = len(w) + (1 if cur > 0 else 0)
            if cur + needed <= capacity:
                cur += needed
            else:
                lines += 1
                cur = len(w)
        return max(1, lines)

    @staticmethod
    def fit_font_size(
        text: str,
        box_w: int,
        box_h: int,
        max_lines: int,
        base_font: int,
        min_font: int,
        rtl: bool,
        line_height: float = 1.35,
    ) -> Tuple[int, int]:
        """
        Reduce font size until:
        - estimated lines <= max_lines
        - total height <= box_h
        Returns (font_size, lines)
        """
        font = int(base_font)
        text = (text or "").strip()

        while font >= min_font:
            lines = TextFit.estimate_lines(text, box_w, font, rtl)
            lines = min(lines, max_lines)  # clamp to avoid huge numbers
            total_h = int(lines * font * line_height)
            if lines <= max_lines and total_h <= box_h:
                return font, lines
            font -= 1

        # fallback
        lines = min(TextFit.estimate_lines(text, box_w, min_font, rtl), max_lines)
        return min_font, lines

# ======================================================
# 🧱 TEXT ENGINE (FOREIGNOBJECT - iOS SAFE)
# ======================================================
class TextEngine:
    @staticmethod
    def foreign_object_block(
        x: int, y: int, w: int, h: int,
        html_text: str,
        font_px: int,
        max_lines: int,
        color: str,
        weight: int,
        rtl: bool,
        align: str = "right",
        line_height: float = 1.35,
    ) -> str:
        """
        Deterministic text box: no overflow, clamp lines.
        """
        safe_html = TextFit._sanitize_html(html_text)

        direction = "rtl" if rtl else "ltr"
        text_align = "right" if rtl else "left"
        if align in ("left", "right", "center"):
            text_align = align

        # Bidi protection: wrap latin tokens with span dir=ltr when RTL
        if rtl:
            safe_html = re.sub(
                r"([A-Za-z0-9][A-Za-z0-9\-\_\.\#\/]*)",
                r'<span dir="ltr">\1</span>',
                safe_html
            )

        return f"""
<foreignObject x="{x}" y="{y}" width="{w}" height="{h}">
  <div xmlns="http://www.w3.org/1999/xhtml" style="
    direction:{direction};
    unicode-bidi:plaintext;
    text-align:{text_align};
    color:{color};
    font-family:'Cairo','Tajawal','Arial',sans-serif;
    font-size:{font_px}px;
    font-weight:{weight};
    line-height:{line_height};
    margin:0;
    padding:0;
    overflow:hidden;
    display:-webkit-box;
    -webkit-line-clamp:{max_lines};
    -webkit-box-orient:vertical;
    word-break:break-word;
  ">{safe_html}</div>
</foreignObject>
""".strip()

# ======================================================
# 📚 ASSET VAULT (LOAD LAYOUTS)
# ======================================================
class AssetVault:
    def __init__(self):
        self.layouts: List[Dict[str, Any]] = []
        self.refresh()

    def refresh(self):
        try:
            if os.path.exists(LAYOUT_FILE):
                with open(LAYOUT_FILE, "r", encoding="utf-8") as f:
                    self.layouts = json.load(f)
                logger.info(f"📚 Loaded layouts: {len(self.layouts)} from layout_sets.json")
            else:
                logger.warning("⚠️ layout_sets.json not found → using fallback layouts")
                self.layouts = self.fallback_layouts()
        except Exception as e:
            logger.error(f"❌ Layout load error: {e}")
            self.layouts = self.fallback_layouts()

    @staticmethod
    def fallback_layouts() -> List[Dict[str, Any]]:
        # Two strong defaults: CURVE + SHARP
        return [
            {
                "id": "fallback_curve_modern",
                "vibes": ["medical", "beauty", "soft", "modern", "ramadan", "food"],
                "structure": {
                    "viewBox": "0 0 595 842",
                    "defs": [],
                    "layers": [
                        {
                            "element": "path",
                            "d_base": "M0,842 L0,480 C120,430 260,620 360,560 C460,500 520,450 595,500 L595,842 Z",
                            "fill": "{{COLOR_1}}",
                            "opacity": 0.12
                        },
                        {
                            "element": "path",
                            "d_base": "M0,842 L0,600 C140,560 240,740 360,690 C470,640 520,610 595,640 L595,842 Z",
                            "fill": "{{COLOR_1}}",
                            "opacity": 0.45
                        },
                        {
                            "element": "path",
                            "d_base": "M0,842 L0,680 C140,650 250,790 360,760 C470,730 520,710 595,730 L595,842 Z",
                            "fill": "{{COLOR_1}}",
                            "opacity": 1.0
                        },
                    ]
                },
                "logic": {
                    "text_safe_area": {"top": 70, "left": 55, "right": 55, "bottom": 120},
                    "title_box_ratio": 0.18,
                    "body_box_ratio": 0.30
                },
                "params": {}
            },
            {
                "id": "fallback_sharp_corporate",
                "vibes": ["corporate", "tech", "finance", "official", "construction"],
                "structure": {
                    "viewBox": "0 0 595 842",
                    "defs": [],
                    "layers": [
                        {
                            "element": "path",
                            "d_base": "M0,0 L595,0 L595,220 L0,165 Z",
                            "fill": "{{COLOR_1}}",
                            "opacity": 1.0
                        },
                        {
                            "element": "path",
                            "d_base": "M0,842 L0,760 L595,640 L595,842 Z",
                            "fill": "{{COLOR_2}}",
                            "opacity": 1.0
                        }
                    ]
                },
                "logic": {
                    "text_safe_area": {"top": 250, "left": 55, "right": 55, "bottom": 130},
                    "title_box_ratio": 0.16,
                    "body_box_ratio": 0.34
                },
                "params": {}
            }
        ]

    def find_best_match(self, user_msg: str) -> Dict[str, Any]:
        msg = (user_msg or "").lower()
        if not self.layouts:
            self.layouts = self.fallback_layouts()

        # vibe matching
        candidates = []
        for l in self.layouts:
            vibes = [str(v).lower() for v in (l.get("vibes", []) or [])]
            if any(v in msg for v in vibes):
                candidates.append(l)

        return random.choice(candidates) if candidates else random.choice(self.layouts)

GLOBAL_VAULT = AssetVault()

# ======================================================
# 🎨 COLOR UTIL (CONTRAST PICK)
# ======================================================
def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hc = (hex_color or "").strip().lstrip("#")
    if len(hc) == 8:  # ignore alpha
        hc = hc[:6]
    if len(hc) != 6:
        return (17, 17, 17)
    return (int(hc[0:2], 16), int(hc[2:4], 16), int(hc[4:6], 16))

def _relative_luminance(rgb: Tuple[int, int, int]) -> float:
    def to_lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * to_lin(r) + 0.7152 * to_lin(g) + 0.0722 * to_lin(b)

def pick_text_color(bg_hex: str) -> str:
    lum = _relative_luminance(_hex_to_rgb(bg_hex))
    return "#111111" if lum > 0.55 else "#FFFFFF"

# ======================================================
# 🧩 GEOMETRY RESOLVER (BUILD SVG FROM LAYOUT + AI)
# ======================================================
class GeometryResolver:
    @staticmethod
    def _parse_viewbox(viewBox: str) -> Tuple[int, int]:
        m = re.search(r"0\s+0\s+(\d+)\s+(\d+)", viewBox or "")
        if m:
            return int(m.group(1)), int(m.group(2))
        return 595, 842

    @staticmethod
    def build_svg(layout: Dict[str, Any], ai: Dict[str, Any], user_msg: str, width: int, height: int, seed: int) -> str:
        structure = layout.get("structure", {}) or {}
        logic = layout.get("logic", {}) or {}

        viewBox = structure.get("viewBox", f"0 0 {width} {height}")
        canvas_w, canvas_h = GeometryResolver._parse_viewbox(viewBox)

        # Override if caller sends dynamic size
        viewBox = f"0 0 {width} {height}"
        canvas_w, canvas_h = width, height

        primary = str(ai.get("primary", "#1A237E")).strip()
        accent = str(ai.get("accent", "#FF5252")).strip()

        # text colors: if AI doesn't supply, choose by contrast vs primary
        title_color = str(ai.get("text_color_title", "")).strip() or pick_text_color(primary)
        body_color = str(ai.get("text_color_body", "")).strip() or "#333333"

        title = str(ai.get("title", "عنوان")).strip()
        body = str(ai.get("body", "تفاصيل...")).strip()

        rtl = contains_arabic(title + " " + body + " " + user_msg)

        # Build defs
        defs_list = structure.get("defs", []) or []
        defs = "\n".join([str(d) for d in defs_list])
        defs = defs.replace("{{COLOR_1}}", primary).replace("{{COLOR_2}}", accent)

        # Resolve params (optional)
        params = {}
        for key, limits in (layout.get("params", {}) or {}).items():
            mn = int(limits.get("min", 0))
            mx = int(limits.get("max", 100))
            params[key] = str(random.Random(seed + hash(key) % 9999).randint(mn, mx))

        # Build layers
        layers_svg = []
        for layer in (structure.get("layers", []) or []):
            element_type = layer.get("element", "path")
            opacity = layer.get("opacity", 1.0)
            fill = str(layer.get("fill", "#000")).replace("{{COLOR_1}}", primary).replace("{{COLOR_2}}", accent)

            if element_type == "path":
                d = str(layer.get("d_base", ""))
                for pk, pv in params.items():
                    d = d.replace(f"{{{{{pk}}}}}", pv)
                layers_svg.append(f'<path d="{d}" fill="{fill}" opacity="{opacity}"/>')
            elif element_type == "circle":
                cx = str(layer.get("cx", "0"))
                cy = str(layer.get("cy", "0"))
                r = str(layer.get("r", "0"))
                layers_svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" opacity="{opacity}"/>')

        # Safe area
        sa = logic.get("text_safe_area", {}) or {}
        top = int(sa.get("top", int(canvas_h * 0.10)))
        left = int(sa.get("left", int(canvas_w * 0.08)))
        right = int(sa.get("right", int(canvas_w * 0.08)))
        bottom = int(sa.get("bottom", int(canvas_h * 0.14)))

        safe_w = max(1, canvas_w - left - right)
        safe_h = max(1, canvas_h - top - bottom)

        # Text boxes ratios (deterministic)
        title_ratio = float(logic.get("title_box_ratio", 0.18))
        body_ratio = float(logic.get("body_box_ratio", 0.32))

        title_h = max(80, int(safe_h * title_ratio))
        body_h = max(160, int(safe_h * body_ratio))

        # Title box
        title_x = left
        title_y = top
        title_w = safe_w

        # Body box
        body_x = left
        body_y = top + title_h + 18
        body_w = safe_w
        body_h = min(body_h, canvas_h - body_y - bottom)

        # AUTO-FIT fonts (this is the key fix)
        # Base sizes tied to canvas width (stable)
        title_base = int(canvas_w * 0.075)  # ~44 on 595
        body_base = int(canvas_w * 0.038)   # ~22 on 595

        title_font, _t_lines = TextFit.fit_font_size(
            title, title_w, title_h, max_lines=2,
            base_font=title_base, min_font=22, rtl=rtl, line_height=1.20
        )
        body_font, _b_lines = TextFit.fit_font_size(
            body, body_w, body_h, max_lines=12,
            base_font=body_base, min_font=14, rtl=rtl, line_height=1.35
        )

        text_svg = []
        text_svg.append(
            TextEngine.foreign_object_block(
                x=title_x, y=title_y, w=title_w, h=title_h,
                html_text=title,
                font_px=title_font, max_lines=2,
                color=title_color, weight=800,
                rtl=rtl, align="right" if rtl else "left",
                line_height=1.20
            )
        )
        text_svg.append(
            TextEngine.foreign_object_block(
                x=body_x, y=body_y, w=body_w, h=body_h,
                html_text=body,
                font_px=body_font, max_lines=12,
                color=body_color, weight=600,
                rtl=rtl, align="right" if rtl else "left",
                line_height=1.35
            )
        )

        svg = f"""
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xhtml="http://www.w3.org/1999/xhtml"
     viewBox="{viewBox}" width="100%" height="100%">
  <defs>{defs}</defs>
  {"".join(layers_svg)}
  {"".join(text_svg)}
</svg>
""".strip()

        # Minify whitespace a bit
        svg = re.sub(r">\s+<", "><", svg)
        return svg

# ======================================================
# 🚀 ROUTES
# ======================================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "Almonjez V40 Deterministic SVG Online ✅",
        "layouts": len(GLOBAL_VAULT.layouts),
    })

@app.route("/gemini", methods=["POST"])
def generate():
    if not client:
        return jsonify({"error": "AI Offline (Missing API Key or init error)"}), 500

    try:
        data = request.json or {}
        user_msg = str(data.get("message", "")).strip()
        width = int(data.get("width", 595))
        height = int(data.get("height", 842))

        seed = random.randint(1000, 999999)
        layout = GLOBAL_VAULT.find_best_match(user_msg)

        # 1) Ask Gemini for JSON Contract ONLY (text + colors)
        system_instruction = f"""
ROLE: Expert Arabic Copywriter + Color Director.
TASK: Return ONLY a valid JSON object. No markdown. No SVG.

Rules:
- Title: max 6 words (Arabic friendly).
- Body: max 40 words.
- Provide two colors: primary and accent (#RRGGBB).
- Provide text colors with strong contrast:
  - text_color_title: (#111111 or #FFFFFF)
  - text_color_body: (#111111 or #333333)

Return JSON exactly:
{{
  "primary": "#1A237E",
  "accent": "#FF5252",
  "text_color_title": "#FFFFFF",
  "text_color_body": "#333333",
  "title": "عنوان جذاب",
  "body": "تفاصيل قصيرة احترافية..."
}}
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg if user_msg else "صمّم عنواناً ونصاً قصيراً احترافياً مع ألوان مناسبة.",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.45,
                max_output_tokens=1024
            )
        )

        ai = Sanitizer.parse_json(response.text or "")
        if not ai:
            return jsonify({"error": "Failed to parse AI JSON contract"}), 500

        # Safety normalize colors
        def _norm_hex(hx: str, fallback: str) -> str:
            hx = (hx or "").strip()
            if not re.match(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$", hx):
                return fallback
            if len(hx) == 9:  # remove alpha
                return "#" + hx[1:7]
            return hx

        ai["primary"] = _norm_hex(ai.get("primary"), "#1A237E")
        ai["accent"] = _norm_hex(ai.get("accent"), "#FF5252")

        # if title color not valid, auto-pick from primary
        ai["text_color_title"] = _norm_hex(ai.get("text_color_title"), pick_text_color(ai["primary"]))
        ai["text_color_body"] = _norm_hex(ai.get("text_color_body"), "#333333")

        # 2) Build deterministic SVG
        svg = GeometryResolver.build_svg(
            layout=layout,
            ai=ai,
            user_msg=user_msg,
            width=width,
            height=height,
            seed=seed
        )

        return jsonify({
            "response": svg,
            "meta": {
                "engine": "V40_Deterministic_SVG",
                "layout_id": layout.get("id", "unknown"),
                "seed": seed,
                "ai_contract": ai
            }
        })

    except Exception as e:
        logger.error(f"Generate error: {e}")
        return jsonify({"error": str(e)}), 500

# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
