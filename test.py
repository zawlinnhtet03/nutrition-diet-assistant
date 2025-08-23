from mistralai import Mistral
import os
from dotenv import load_dotenv
import json
import re
from typing import Dict, Any, Optional, List

load_dotenv()
client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

SCHEMA = '{"calories": int, "protein_g": int, "carbs_g": int, "fats_g": int, "meals": {"breakfast": str, "lunch": str, "snack": str, "dinner": str}, "notes": str}'

INSTRUCTION = (
    "You are a nutrition assistant. Given the user’s profile, recommend a daily macro breakdown and food suggestions. "
    "Respect allergies, current goals, and dietary preferences (e.g., halal). Keep outputs consistent and realistic. "
    f"Return ONLY minified JSON (no markdown, no commentary) with this schema: {SCHEMA}. "
    "All numbers should be whole integers. Ensure calories ≈ 4*protein_g + 4*carbs_g + 9*fats_g (±10%)."
)

PROMPT_TMPL = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{}

### Input:
{}

### Response:
"""

def _to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None or value == "":
            return default
        return int(round(float(value)))
    except Exception:
        return default

def validate_and_defaults(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce types, clamp ranges, and provide sensible defaults."""
    f = dict(fields or {})
    f.setdefault("Allergies", "None")
    f.setdefault("Dietary_Preferences", "")
    f.setdefault("Current_Goals", "General health")

    # Coerce numerics
    f["Age"] = _to_int(f.get("Age"))
    f["Height_cm"] = _to_int(f.get("Height_cm"))
    f["Weight_kg"] = _to_int(f.get("Weight_kg"))
    # BMI optional; if missing and height/weight present, leave it to the model
    try:
        bmi = float(f.get("BMI")) if f.get("BMI") not in (None, "") else None
        f["BMI"] = round(bmi, 1) if bmi is not None else ""
    except Exception:
        f["BMI"] = ""

    # Clamp simple ranges
    if f.get("Age") is not None:
        f["Age"] = max(10, min(100, f["Age"]))
    if f.get("Height_cm") is not None:
        f["Height_cm"] = max(120, min(220, f["Height_cm"]))
    if f.get("Weight_kg") is not None:
        f["Weight_kg"] = max(35, min(250, f["Weight_kg"]))

    return f

def serialize_input(fields: dict) -> str:
    # fields keys: Age, Gender, Height_cm, Weight_kg, BMI, Allergies, Daily_Steps, Sleep_Hours,
    # Current_Goals, Dietary_Preferences, Exercise_Frequency, Preferred_Cuisine, Food_Aversions,
    # Chronic_Disease, Blood_Pressure, Cholesterol_Level, Blood_Sugar_Level
    fields = validate_and_defaults(fields)
    get = lambda k, d="": ("" if fields.get(k) is None else str(fields.get(k, d)))
    parts = [
        f"Age: {get('Age')}",
        f"Gender: {get('Gender')}",
        f"Height_cm: {get('Height_cm')}",
        f"Weight_kg: {get('Weight_kg')}",
        f"BMI: {get('BMI')}",
        f"Allergies: {get('Allergies','None')}",
        f"Daily_Steps: {get('Daily_Steps')}",
        f"Sleep_Hours: {get('Sleep_Hours')}",
        f"Current_Goals: {get('Current_Goals')}",
        f"Dietary_Preferences: {get('Dietary_Preferences')}",
        f"Exercise_Frequency: {get('Exercise_Frequency','')}",
        f"Preferred_Cuisine: {get('Preferred_Cuisine','')}",
        f"Food_Aversions: {get('Food_Aversions','')}",
        f"Chronic_Disease: {get('Chronic_Disease','')}",
        f"Blood_Pressure: {get('Blood_Pressure','')}",
        f"Cholesterol_Level: {get('Cholesterol_Level','')}",
        f"Blood_Sugar_Level: {get('Blood_Sugar_Level','')}",
    ]
    return "\n".join(parts)

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try to find the first {...} block
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None

def get_plan_json(fields: dict, model: str = "mistral-small-latest") -> Dict[str, Any]:
    user_input = serialize_input(fields)
    # Add extra constraints that the model should follow
    constrained_instruction = INSTRUCTION + " Ensure halal compliance when requested and strictly avoid listed allergens. If fat loss is the goal, set calories below maintenance."
    prompt = PROMPT_TMPL.format(constrained_instruction, user_input, "")
    resp = client.chat.complete(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    content = resp.choices[0].message.content
    parsed = _extract_json(content)
    return parsed if parsed is not None else {"raw": content}

def batch_score_csv(input_csv: str, output_csv: str, model: str = "mistral-small-latest") -> None:
    """Read user rows from CSV and write a CSV with a plan_json column for QA."""
    import pandas as pd
    df = pd.read_csv(input_csv)
    plans: List[str] = []
    for _, row in df.iterrows():
        fields = row.to_dict()
        plan = get_plan_json(fields, model=model)
        plans.append(json.dumps(plan, ensure_ascii=False))
    df_out = df.copy()
    df_out["plan_json"] = plans
    df_out.to_csv(output_csv, index=False)

# Example usage from your UI form (single request):
if __name__ == "__main__":
    sample = {
        "Age": 28, "Gender": "Male", "Height_cm": 178, "Weight_kg": 80, "BMI": 25.3,
        "Allergies": "Peanuts", "Daily_Steps": 7000, "Sleep_Hours": 7,
        "Current_Goals": "Muscle gain", "Dietary_Preferences": "High-protein, halal",
    }
    result = get_plan_json(sample)
    print(json.dumps(result, ensure_ascii=False))
    # Batch scoring example (uncomment to run):
    # batch_score_csv("diet_data.csv", "diet_plans_scored.csv")