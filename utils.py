import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import os
import json
from typing import List, Dict, Any, Optional

import httpx
from dotenv import load_dotenv

# Optional: LLM for ingredient extraction (Mistral)
try:
    from mistralai.client import MistralClient
    from mistralai.models.chat_completion import ChatMessage
except Exception:  # pragma: no cover
    MistralClient = None
    ChatMessage = None
try:
    # Older SDK alias
    from mistralai import Mistral as LegacyMistralClient
except Exception:  # pragma: no cover
    LegacyMistralClient = None

load_dotenv()

def generate_mock_nutrition_data():
    """Generate mock nutrition data for dashboard visualization"""
    # Generate weekly nutrition data
    dates = pd.date_range(start=datetime.now() - timedelta(days=6), end=datetime.now(), freq='D')
    
    nutrition_data = []
    for date in dates:
        nutrition_data.append({
            'date': date,
            'calories': random.randint(1800, 2400),
            'protein': random.randint(80, 150),
            'carbs': random.randint(180, 300),
            'fat': random.randint(50, 100),
            'fiber': random.randint(15, 35),
            'water_liters': round(random.uniform(1.5, 3.5), 1)
        })
    
    return pd.DataFrame(nutrition_data)

def create_nutrition_charts(nutrition_df):
    """Create various nutrition charts for the dashboard"""
    charts = {}

# Minimal known food vocabulary to validate free-text inputs
KNOWN_FOODS = {
    # staples
    "rice","chicken","egg","tofu","potato","pork","salad","bread","noodle","noodles","pasta",
    "beef","fish","shrimp","prawn","milk","yogurt","banana","apple","avocado","oil","butter","cheese",
    # vegetables
    "spinach","broccoli","cabbage","tomato","onion","garlic","okra","carrot","pepper",
    # SEA/Chinese dishes
    "mala xiang guo","hot pot","noodle soup","fried rice","fried noodles","laksa","pho","ramen",
    # Myanmar/local
    "mohinga","laphet","shan noodles",
}

def looks_like_meal_text(text: str) -> bool:
    """Heuristic: require a digit or a known food keyword to proceed."""
    if not text:
        return False
    t = text.lower()
    if any(ch.isdigit() for ch in t):
        return True
    return any(word in t for word in KNOWN_FOODS)
    
    # Daily calories chart
    charts['calories'] = px.line(
        nutrition_df, 
        x='date', 
        y='calories',
        title='Daily Calorie Intake',
        markers=True
    )
    
    # Macronutrient breakdown (pie chart)
    latest_data = nutrition_df.iloc[-1]
    charts['macros'] = px.pie(
        values=[latest_data['protein'] * 4, latest_data['fat'] * 9, latest_data['carbs'] * 4],
        names=['Protein', 'Fat', 'Carbohydrates'],
        title='Today\'s Macronutrient Distribution (Calories)'
    )
    
    # Weekly trends (multi-line)
    charts['trends'] = px.line(
        nutrition_df,
        x='date',
        y=['calories', 'protein', 'carbs', 'fat'],
        title='Weekly Nutrition Trends'
    )
    
    return charts

def calculate_bmr(weight_kg, height_cm, age, gender):
    """Calculate Basal Metabolic Rate using Mifflin-St Jeor Equation"""
    if gender.lower() == 'male':
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    
    return bmr

def calculate_tdee(bmr, activity_level):
    """Calculate Total Daily Energy Expenditure"""
    activity_multipliers = {
        'sedentary': 1.2,
        'lightly_active': 1.375,
        'moderately_active': 1.55,
        'very_active': 1.725,
        'extremely_active': 1.9
    }
    
    multiplier = activity_multipliers.get(activity_level.lower().replace(' ', '_'), 1.55)
    return bmr * multiplier

def get_nutrition_recommendation(calories, protein, carbs, fat, user_goals):
    """Generate nutrition recommendations based on intake and goals"""
    recommendations = []
    
    # Protein recommendations
    if protein < 0.8:  # per kg body weight (approximate)
        recommendations.append("💪 Consider increasing protein intake for better muscle maintenance")
    elif protein > 2.0:
        recommendations.append("⚖️ Your protein intake is quite high - ensure you're staying hydrated")
    
    # Calorie recommendations
    if calories < 1200:
        recommendations.append("⚠️ Your calorie intake seems low - consult a healthcare provider")
    elif calories > 3000:
        recommendations.append("📊 High calorie intake - make sure it aligns with your activity level")
    
    # Fat recommendations
    fat_percentage = (fat * 9) / calories * 100
    if fat_percentage < 20:
        recommendations.append("🥑 Consider adding healthy fats like avocados, nuts, or olive oil")
    elif fat_percentage > 35:
        recommendations.append("🍃 Try incorporating more lean proteins and complex carbs")
    
    # Goal-specific recommendations
    if user_goals == 'weight_loss':
        recommendations.append("🎯 For weight loss: Focus on a moderate calorie deficit with adequate protein")
    elif user_goals == 'muscle_gain':
        recommendations.append("💪 For muscle gain: Ensure adequate protein and slight calorie surplus")
    elif user_goals == 'maintenance':
        recommendations.append("⚖️ For maintenance: Your intake looks balanced - keep up the good work!")
    
    return recommendations

def format_nutrition_display(calories, protein, carbs, fat, fiber=None, sugar=None):
    """Format nutrition information for display"""
    nutrition_info = f"""
    **🔥 Calories:** {calories:.0f} kcal
    **🥩 Protein:** {protein:.1f}g
    **🍞 Carbohydrates:** {carbs:.1f}g
    **🧈 Fat:** {fat:.1f}g
    """
    
    if fiber is not None:
        nutrition_info += f"\n**🌾 Fiber:** {fiber:.1f}g"
    
    if sugar is not None:
        nutrition_info += f"\n**🍯 Sugar:** {sugar:.1f}g"
    
    return nutrition_info

def get_meal_timing_advice(meal_time):
    """Provide meal timing advice based on time of day"""
    hour = meal_time.hour
    
    if 5 <= hour < 10:
        return "🌅 Great timing for breakfast! This will kickstart your metabolism for the day."
    elif 10 <= hour < 14:
        return "☀️ Perfect lunch timing! This should keep you energized for the afternoon."
    elif 14 <= hour < 18:
        return "🌤️ Good afternoon snack time! Keep it light and nutritious."
    elif 18 <= hour < 22:
        return "🌆 Dinner time! Try to finish eating 2-3 hours before bedtime."
    else:
        return "🌙 Late night eating! Consider lighter options to support better sleep."

def validate_nutrition_input(calories, protein, carbs, fat):
    """Validate nutrition input values"""
    errors = []
    
    if calories <= 0:
        errors.append("Calories must be greater than 0")
    
    if protein < 0:
        errors.append("Protein cannot be negative")
    
    if carbs < 0:
        errors.append("Carbohydrates cannot be negative")
    
    if fat < 0:
        errors.append("Fat cannot be negative")
    
    # Check if macros add up reasonably to calories
    calculated_calories = (protein * 4) + (carbs * 4) + (fat * 9)
    if abs(calculated_calories - calories) > calories * 0.2:  # 20% tolerance
        errors.append("Macronutrient values don't align well with total calories")
    
    return errors

def generate_meal_suggestions(dietary_restrictions, health_goals, cuisine_preference=None):
    """Generate meal suggestions based on user preferences"""
    suggestions = {
        'breakfast': [],
        'lunch': [],
        'dinner': [],
        'snacks': []
    }
    
    # Base suggestions
    base_meals = {
        'breakfast': [
            "Greek yogurt with berries and granola",
            "Oatmeal with banana and nuts",
            "Scrambled eggs with vegetables",
            "Smoothie bowl with protein powder"
        ],
        'lunch': [
            "Grilled chicken salad with mixed greens",
            "Quinoa bowl with roasted vegetables",
            "Turkey and avocado wrap",
            "Lentil soup with whole grain bread"
        ],
        'dinner': [
            "Baked salmon with steamed broccoli",
            "Lean beef stir-fry with brown rice",
            "Grilled chicken with roasted sweet potato",
            "Vegetarian pasta with marinara sauce"
        ],
        'snacks': [
            "Apple slices with almond butter",
            "Greek yogurt with honey",
            "Mixed nuts and dried fruit",
            "Vegetable sticks with hummus"
        ]
    }
    
    # Filter based on dietary restrictions and goals
    for meal_type, meals in base_meals.items():
        filtered_meals = meals.copy()
        
        # Apply dietary restriction filters
        if 'vegetarian' in [r.lower() for r in dietary_restrictions]:
            filtered_meals = [meal for meal in filtered_meals if 'chicken' not in meal.lower() and 'beef' not in meal.lower() and 'salmon' not in meal.lower()]
        
        if 'gluten-free' in [r.lower() for r in dietary_restrictions]:
            filtered_meals = [meal for meal in filtered_meals if 'bread' not in meal.lower() and 'pasta' not in meal.lower()]
        
        suggestions[meal_type] = filtered_meals[:3]  # Limit to top 3 suggestions
    
    return suggestions

# -----------------------------
# Meal Analyzer helpers (LLM+USDA)
# -----------------------------
# Meal Analyzer helpers (LLM+USDA)
# -----------------------------

FDC_API_KEY = os.getenv("FDC_API_KEY", "")

_BASIC_GRAM_MAP = {
    # fallback grams per unit for common items
    ("egg", "piece"): 50,
    ("bread", "slice"): 30,
    ("rice", "cup"): 180,
    ("rice", "bowl"): 200,
    ("noodles", "bowl"): 220,
    ("noodle", "bowl"): 220,
    ("chicken", "cup"): 140,
}

def convert_to_grams(quantity: float, unit: str, food_name: str) -> float:
    unit = (unit or "").lower().strip()
    name = (food_name or "").lower().strip()
    if unit in ["g", "gram", "grams"]:
        return float(quantity)
    if unit in ["kg", "kilogram", "kilograms"]:
        return float(quantity) * 1000.0
    if unit in ["ml"]:
        # approx: 1 ml ~ 1 g for water-like; best-effort fallback
        return float(quantity)
    if unit in ["l", "liter", "litre"]:
        return float(quantity) * 1000.0
    if unit in ["cup", "cups"]:
        # try to use food-specific mapping; default 240g
        base = 240.0
        base = _BASIC_GRAM_MAP.get((name, "cup"), base)
        return float(quantity) * base
    if unit in ["bowl", "bowls"]:
        # use food-specific mapping; default 250g
        base = 250.0
        base = _BASIC_GRAM_MAP.get((name, "bowl"), base)
        return float(quantity) * base
    if unit in ["tbsp", "tablespoon", "tablespoons"]:
        return float(quantity) * 15.0
    if unit in ["tsp", "teaspoon", "teaspoons"]:
        return float(quantity) * 5.0
    if unit in ["piece", "pieces", "pc"]:
        base = _BASIC_GRAM_MAP.get((name, "piece"), 50.0)
        return float(quantity) * base
    if unit in ["slice", "slices"]:
        base = _BASIC_GRAM_MAP.get((name, "slice"), 30.0)
        return float(quantity) * base
    # default: assume grams
    return float(quantity)


def extract_ingredients_free_text(text: str) -> Dict[str, Any]:
    """Extract structured ingredients from free text using Mistral.
    Returns dict: {"items": [{"name","quantity","unit"}], "notes": str}
    """
    text = (text or "").strip()
    if not text:
        return {"items": [], "notes": ""}

    api_key = os.getenv("MISTRAL_API_KEY") or os.getenv("MISTRALAI_API_KEY") or os.getenv("MISTRAL_TOKEN")
    model_name = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
    if (MistralClient or LegacyMistralClient) and api_key:
        try:
            raw = "{}"
            if MistralClient is not None:
                client = MistralClient(api_key=api_key)
                schema_hint = (
                    "Return ONLY JSON with this exact shape: "
                    "{\"items\":[{\"name\":string,\"quantity\":number,\"unit\":string}],\"notes\":string}. "
                    "items should include only edible foods actually mentioned. "
                    "Support multi-word dishes, and common units: g, kg, ml, l, cup, bowl, tbsp, tsp, piece, slice. "
                    "If the unit is a volume/portion (cup/bowl/piece/slice) keep it as provided; do NOT convert to grams. "
                    "Infer a reasonable quantity when obvious (e.g., '2 eggs' => quantity=2, unit='piece'). "
                    "If nothing edible is found, return {\"items\":[],\"notes\":\"no_food_found\"}."
                )
                prompt = (
                    "You are a nutrition extraction assistant. "
                    "Extract foods with quantities/units from the text below.\n\n"
                    f"TEXT:\n{text}\n\n"
                    f"{schema_hint}"
                )
                resp = client.chat(
                    model=model_name,
                    messages=[
                        ChatMessage(role="system", content="You are a nutrition extraction assistant."),
                        ChatMessage(role="user", content=prompt),
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                raw = resp.choices[0].message.content if getattr(resp, "choices", None) else "{}"
            elif LegacyMistralClient is not None:
                client = LegacyMistralClient(api_key=api_key)
                schema_hint = (
                    "Return ONLY JSON with this exact shape: "
                    "{\"items\":[{\"name\":string,\"quantity\":number,\"unit\":string}],\"notes\":string}. "
                    "items should include only edible foods actually mentioned. "
                    "Support multi-word dishes, and common units: g, kg, ml, l, cup, bowl, tbsp, tsp, piece, slice. "
                    "If the unit is a volume/portion (cup/bowl/piece/slice) keep it as provided; do NOT convert to grams. "
                    "Infer a reasonable quantity when obvious (e.g., '2 eggs' => quantity=2, unit='piece'). "
                    "If nothing edible is found, return {\"items\":[],\"notes\":\"no_food_found\"}."
                )
                prompt = (
                    "You are a nutrition extraction assistant. "
                    "Extract foods with quantities/units from the text below.\n\n"
                    f"TEXT:\n{text}\n\n"
                    f"{schema_hint}"
                )
                # Legacy client exposes .chat.complete
                resp = client.chat.complete(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a nutrition extraction assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                raw = resp.choices[0].message.content if getattr(resp, "choices", None) else "{}"
            data = json.loads(raw)
            items = data.get("items", []) if isinstance(data, dict) else []
            # sanitize
            cleaned = []
            for it in items:
                name = str(it.get("name", "")).strip()
                try:
                    qty = float(it.get("quantity", 0))
                except Exception:
                    qty = 0.0
                unit = str(it.get("unit", "g")).strip() or "g"
                if name and qty > 0:
                    cleaned.append({"name": name, "quantity": qty, "unit": unit})
            return {"items": cleaned, "notes": data.get("notes", "")}
        except Exception:
            return {"items": [], "notes": "llm_error"}

    # No Mistral available
    return {"items": [], "notes": "llm_unavailable"}

def _fdc_search(name: str) -> Dict[str, Any]:
    if not FDC_API_KEY:
        return {}
    try:
        r = httpx.get(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params={
                "api_key": FDC_API_KEY,
                "query": name,
                "pageSize": 5,
                # prefer more standardized sources first
                "dataType": ["Survey (FNDDS)", "SR Legacy", "Branded"],
            },
            timeout=10.0,
        )
        data = r.json() or {}
        foods = data.get("foods") or []
        if not foods:
            return {}
        # Choose the highest score; fall back to first
        best = max(foods, key=lambda f: float(f.get("score", 0)))
        return best
    except Exception:
        return {}


def _extract_per100g(food: Dict[str, Any]) -> Dict[str, float]:
    # Map using FDC nutrientNumbers for stability
    # 1008=Energy(kcal), 1003=Protein(g), 1004=Total lipid (fat)(g), 1005=Carbohydrate(g),
    # 1079=Fiber(g), 2000=Sugars total(g), 1093=Sodium(mg)
    targets = {
        "1008": ("calories", 0.0),
        "1003": ("protein_g", 0.0),
        "1004": ("fat_g", 0.0),
        "1005": ("carbs_g", 0.0),
        "1079": ("fiber_g", 0.0),
        "2000": ("sugar_g", 0.0),
        "1093": ("sodium_mg", 0.0),
    }
    nutrients = {k: v for k, v in [
        ("calories", 0.0), ("protein_g", 0.0), ("carbs_g", 0.0), ("fat_g", 0.0), ("fiber_g", 0.0), ("sugar_g", 0.0), ("sodium_mg", 0.0)
    ]}
    if not food:
        return nutrients
    for n in (food.get("foodNutrients") or []):
        num = str(n.get("nutrientNumber") or "").strip()
        val = n.get("value")
        try:
            val_f = float(val)
        except Exception:
            val_f = 0.0
        if num in targets:
            key, _ = targets[num]
            nutrients[key] = val_f
        else:
            # Name-based fallbacks if nutrientNumber absent
            name = (n.get("nutrientName") or "").lower()
            if ("energy" in name or name == "calories") and nutrients["calories"] == 0.0:
                nutrients["calories"] = val_f
            elif ("protein" in name) and nutrients["protein_g"] == 0.0:
                nutrients["protein_g"] = val_f
            elif (("total lipid" in name) or ("total fat" in name) or (" fat" in name)) and ("saturated" not in name) and nutrients["fat_g"] == 0.0:
                nutrients["fat_g"] = val_f
            elif ("carbohydrate" in name) and nutrients["carbs_g"] == 0.0:
                nutrients["carbs_g"] = val_f
            elif ("fiber" in name) and nutrients["fiber_g"] == 0.0:
                nutrients["fiber_g"] = val_f
            elif (("sugars" in name) or name == "sugar") and nutrients["sugar_g"] == 0.0:
                nutrients["sugar_g"] = val_f
            elif ("sodium" in name) and nutrients["sodium_mg"] == 0.0:
                nutrients["sodium_mg"] = val_f
    return nutrients


def _rough_local_lookup(item: Dict[str, Any]) -> Optional[Dict[str, float]]:
    # very rough fallback table per 100g
    name = (item.get("name") or "").lower()
    table = {
        "rice": {"calories": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3, "fiber_g": 0.4, "sugar_g": 0},
        "chicken": {"calories": 165, "protein_g": 31, "carbs_g": 0, "fat_g": 3.6, "fiber_g": 0, "sugar_g": 0},
        "egg": {"calories": 143, "protein_g": 13, "carbs_g": 1.1, "fat_g": 9.5, "fiber_g": 0, "sugar_g": 1.1},
        "tofu": {"calories": 76, "protein_g": 8, "carbs_g": 1.9, "fat_g": 4.8, "fiber_g": 0.3, "sugar_g": 0.6},
        "potato": {"calories": 77, "protein_g": 2, "carbs_g": 17, "fat_g": 0.1, "fiber_g": 2.2, "sugar_g": 0.8},
        "pork": {"calories": 242, "protein_g": 27, "carbs_g": 0, "fat_g": 14, "fiber_g": 0, "sugar_g": 0},
        "salad": {"calories": 20, "protein_g": 1.5, "carbs_g": 3.5, "fat_g": 0.2, "fiber_g": 1.8, "sugar_g": 1.5},
        "noodles": {"calories": 138, "protein_g": 5.0, "carbs_g": 25.0, "fat_g": 2.5, "fiber_g": 1.2, "sugar_g": 0.8},
        "mala xiang guo": {"calories": 200, "protein_g": 8.0, "carbs_g": 8.0, "fat_g": 14.0, "fiber_g": 1.5, "sugar_g": 2.0},
    }
    base = table.get(name)
    if not base:
        # try startswith match
        for k, v in table.items():
            if name.startswith(k):
                base = v
                break
    if not base:
        # Unknown in our small table
        return None
    grams = convert_to_grams(item.get("quantity", 100), item.get("unit", "g"), item.get("name", ""))
    factor = grams / 100.0
    return {k: round(v * factor, 2) for k, v in base.items()} | {"sodium_mg": 0.0}


def compute_nutrition(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "fiber_g": 0.0, "sugar_g": 0.0, "sodium_mg": 0.0}
    details = []
    if not FDC_API_KEY:
        return {"totals": totals, "details": details, "notes": "fdc_unavailable"}
    for it in items:
        food = _fdc_search(it.get("name", ""))
        if not food:
            continue
        per100 = _extract_per100g(food)
        grams = convert_to_grams(it.get("quantity", 100), it.get("unit", "g"), it.get("name", ""))
        factor = grams / 100.0
        nutrients = {k: round(v * factor, 2) for k, v in per100.items()}
        fdc_id = food.get("fdcId")
        for k in totals:
            totals[k] += nutrients.get(k, 0.0)
        details.append({"item": it, "nutrients": nutrients, "fdcId": fdc_id})
    totals = {k: round(v, 2) for k, v in totals.items()}
    return {"totals": totals, "details": details}
