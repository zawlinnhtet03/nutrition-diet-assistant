import os
from datetime import datetime
from typing import Any
import streamlit as st
from PIL import Image

from food_vision import NutriNetVision
from utils import extract_ingredients_free_text, compute_nutrition

def render_analyzer_page(db_manager: Any):
    st.header("Meal Analyzer")
    st.markdown(
        "Analyze your meals for nutrition content and get personalized recommendations"
    )

    st.subheader("📝 Meal Description")
    meal_description = st.text_area(
        "Describe your meal(What do you eat today):",
        placeholder="e.g., 1 bowl of chicken curry with rice and salad",
        height=100,
    )

    
    analyze_text = st.button("🔍 Analyze Meal")

    st.subheader("📸 Meal Photo")
    uploaded_file = st.file_uploader(
        "Upload a photo of your meal (optional)", type=["png", "jpg", "jpeg"]
    )

    if uploaded_file is not None:
        try:
            fname = getattr(uploaded_file, "name", "image")
            st.caption(f"Uploaded: {fname}")
        except Exception:
            pass

    # st.divider()

    # btn_col1, btn_col2 = st.columns([1, 1])
    # analyze_text = btn_col1.button("🔍 Analyze Meal", type="primary")
    analyze_image = st.button("🖼️ Analyze Image")

    if analyze_text:
        if not meal_description:
            st.error("Please describe your meal first!")
        else:
            extraction = extract_ingredients_free_text(meal_description)
            if isinstance(extraction, dict):
                note = extraction.get("notes", "")
                if note in ("llm_unavailable", "llm_error"):
                    st.error(
                        "Text parsing requires LLM. Please set LLM_API_KEY and try again."
                    )
                    st.stop()
            items = (
                extraction.get("items", []) if isinstance(extraction, dict) else []
            )
            if not items:
                st.warning(
                    "Couldn't parse ingredients. Try listing items with quantities, e.g., '150g chicken, 1 cup rice'."
                )
                st.stop()

            result = compute_nutrition(items)
            totals = result.get("totals", {})
            details = result.get("details", [])
            if not details or all(v == 0 for v in totals.values()):
                st.warning("No recognizable foods found. Please refine your description.")
                st.stop()

            st.subheader("🧾 Parsed Ingredients")
            rows = []
            for d in details:
                it = d.get("item", {})
                nut = d.get("nutrients", {})
                rows.append(
                    {
                        "Item": it.get("name", "-"),
                        "Qty": it.get("quantity", "-"),
                        "Unit": it.get("unit", "-"),
                        "kcal": nut.get("calories", 0),
                        "Protein(g)": nut.get("protein_g", 0),
                        "Carbs(g)": nut.get("carbs_g", 0),
                        "Fat(g)": nut.get("fat_g", 0),
                        "Fiber(g)": nut.get("fiber_g", 0),
                        "Sugar(g)": nut.get("sugar_g", 0),
                    }
                )
            st.dataframe(rows, width='stretch')

            st.subheader("📊 Estimated Totals")
            st.info(
                f"Calories: {totals.get('calories',0)} kcal | "
                f"Protein: {totals.get('protein_g',0)} g | "
                f"Carbs: {totals.get('carbs_g',0)} g | "
                f"Fat: {totals.get('fat_g',0)} g | "
                f"Fiber: {totals.get('fiber_g',0)} g | "
                f"Sugar: {totals.get('sugar_g',0)} g"
            )

            if st.session_state.user_data and details:
                meal_log_id = db_manager.save_meal_log(
                    st.session_state.user_data["id"],
                    meal_description,
                    uploaded_file.name if uploaded_file else None,
                )
                db_manager.save_nutrition_analysis(
                    meal_log_id,
                    calories=totals.get("calories", 0),
                    protein=totals.get("protein_g", 0),
                    carbs=totals.get("carbs_g", 0),
                    fat=totals.get("fat_g", 0),
                    recommendation="Auto-estimated from ingredients",
                    sugar=totals.get("sugar_g", 0),
                    fiber=totals.get("fiber_g", 0),
                )

    if analyze_image:
        if uploaded_file is None:
            st.warning("Upload a meal photo first.")
        else:
            try:
                if "nutrinet_vision" not in st.session_state:
                    with st.spinner("Loading food vision model..."):
                        st.session_state.nutrinet_vision = NutriNetVision()

                image = Image.open(uploaded_file).convert("RGB")
                st.image(image, caption="Meal photo", width=400)

                with st.spinner("Analyzing image..."):
                    results = st.session_state.nutrinet_vision.analyze_image(image)

                if not results:
                    st.error("No result from image analyzer.")
                else:
                    item = results[0]
                    name = item.get("name", "unknown_food")
                    conf = float(item.get("confidence", 0.0))
                    portion = float(item.get("portion", 0.0))
                    advice = item.get("health_advice", "")

                    if not os.getenv("FDC_API_KEY"):
                        st.error(
                            "Image nutrition requires USDA FDC. Please set FDC_API_KEY in your environment and try again."
                        )
                        st.stop()

                    if not name or name.startswith("class_") or portion <= 0:
                        st.error(
                            "Could not derive a valid food name/portion from the image. Try another image."
                        )
                        st.stop()

                    fdc_payload = [{"name": name, "quantity": portion, "unit": "g"}]
                    fdc_result = compute_nutrition(fdc_payload) or {}
                    nutrition = fdc_result.get("totals") or {}
                    fdc_details = fdc_result.get("details") or []
                    if not fdc_details or not any(v > 0 for v in nutrition.values()):
                        st.error(
                            "USDA FDC did not return nutrition for this prediction. Try another image or different lighting."
                        )
                        st.stop()

                    st.success(f"Prediction: {name} ({conf*100:.1f}% confidence)")
                    st.caption(f"Estimated portion: {int(round(portion))} g")

                    st.subheader("📊 Estimated Nutrition (scaled)")
                    rows = [
                        {
                            "Calories (kcal)": nutrition.get("calories", 0),
                            "Protein (g)": nutrition.get("protein_g", 0),
                            "Carbs (g)": nutrition.get("carbs_g", 0),
                            "Fat (g)": nutrition.get("fat_g", 0),
                            "Fiber (g)": nutrition.get("fiber_g", 0),
                        }
                    ]
                    st.dataframe(rows, width='stretch')

                    if advice:
                        st.info(f"💡 {advice}")

                    if st.session_state.user_data:
                        meal_desc = meal_description or f"Image: {name}"
                        meal_log_id = db_manager.save_meal_log(
                            st.session_state.user_data["id"],
                            meal_desc,
                            (
                                uploaded_file.name
                                if hasattr(uploaded_file, "name")
                                else None
                            ),
                        )
                        db_manager.save_nutrition_analysis(
                            meal_log_id,
                            calories=float(nutrition.get("calories", 0) or 0),
                            protein=float(nutrition.get("protein_g", 0) or 0),
                            carbs=float(nutrition.get("carbs_g", 0) or 0),
                            fat=float(nutrition.get("fat_g", 0) or 0),
                            recommendation="Image-based estimate (Food-101)",
                            sugar=float(nutrition.get("sugar_g", 0) or 0),
                            fiber=float(nutrition.get("fiber_g", 0) or 0),
                        )
                        st.success("Saved analysis to your log.")
                    else:
                        st.info("Login to save this analysis to your history.")
            except Exception as e:
                st.error(f"Image analysis failed: {e}")

    st.divider()
    st.subheader("📒 Today's Logged Meals")
    if st.session_state.user_data:
        _uid = st.session_state.user_data["id"]
        today_utc = datetime.utcnow().date()
        logs = db_manager.get_user_meal_logs(_uid, limit=100) or []
        rows = []
        entries = []
        totals_today = {
            "calories": 0.0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
            "sugar_g": 0.0,
        }
        for m in logs:
            try:
                mt = m.get("meal_time")
                dt_utc = (
                    datetime.fromisoformat(mt.replace("Z", "+00:00"))
                    if isinstance(mt, str)
                    else datetime.utcnow()
                )
                if dt_utc.date() != today_utc:
                    continue
            except Exception:
                continue
            ana = db_manager.get_nutrition_analysis_by_meal(m.get("id")) or {}
            cal = float(ana.get("calories", 0) or 0)
            pr = float(ana.get("protein_g", 0) or 0)
            cb = float(ana.get("carbs_g", 0) or 0)
            ft = float(ana.get("fat_g", 0) or 0)
            fib = float(ana.get("fiber_g", 0) or 0)
            sug = float(ana.get("sugar_g", 0) or 0)
            row = {
                "Description": m.get("meal_description", "-"),
                "Calories (kcal)": round(cal, 1),
                "Protein (g)": round(pr, 1),
                "Carbs (g)": round(cb, 1),
                "Fat (g)": round(ft, 1),
                "Fiber (g)": round(fib, 1),
                "Sugar (g)": round(sug, 1),
            }
            rows.append(row)
            entries.append({"id": m.get("id"), **row})
            totals_today["calories"] += cal
            totals_today["protein_g"] += pr
            totals_today["carbs_g"] += cb
            totals_today["fat_g"] += ft
            totals_today["fiber_g"] += fib
            totals_today["sugar_g"] += sug

        if rows:
            with st.expander("Maintenance", expanded=False):
                if st.button("Clear previous days", key="clear_prev_days"):
                    ok = db_manager.delete_user_meals_not_today(
                        _uid, today_utc.isoformat()
                    )
                    if ok:
                        st.success("Cleared older entries.")
                        try:
                            st.rerun()
                        except Exception:
                            st.experimental_rerun()
                    else:
                        st.error("Failed to clear older entries.")
            st.caption("Remove any test entries; this deletes the meal and its analysis.")
            for entry in entries:
                with st.container():
                    c1, c2, c3 = st.columns([6, 4, 1])
                    with c1:
                        st.write(f"{entry['Description']}")
                    with c2:
                        st.write(
                            f"{entry['Calories (kcal)']} kcal · "
                            f"Protein: {entry['Protein (g)']} g · "
                            f"Carbs: {entry['Carbs (g)']} g · "
                            f"Fat: {entry['Fat (g)']} g"
                        )
                    with c3:
                        if st.button("Remove", key=f"remove_{entry['id']}"):
                            ok = db_manager.delete_meal_log(entry["id"])
                            if ok:
                                st.success("Removed entry.")
                                try:
                                    st.rerun()
                                except Exception:
                                    st.experimental_rerun()
                            else:
                                st.error("Failed to remove entry.")
        else:
            st.info("No meals logged today. Analyze a meal above to see it here.")
    else:
        st.info("Please log in to view your meal analyses.")
