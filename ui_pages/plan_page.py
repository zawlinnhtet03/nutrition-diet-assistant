import json
from datetime import datetime
import streamlit as st

from meal import get_plan_json

def render_plan_page(db_manager):
    st.header("⚖️ AI Nutrition Plan")
    st.markdown(
        "Fill in your details to generate a personalized daily nutrition plan."
    )

    st.markdown("### 👤 Personal Information")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        age = st.number_input(
            "Age", min_value=10, max_value=100, value=25, key="plan_age"
        )
    with c2:
        gender = st.selectbox(
            "Gender", ["Male", "Female", "Other"], key="plan_gender"
        )
    with c3:
        height = st.number_input(
            "Height (cm)", min_value=120, max_value=220, value=170, key="plan_height"
        )
    with c4:
        weight = st.number_input(
            "Weight (kg)", min_value=35.0, max_value=250.0, value=70.0, step=0.1, key="plan_weight"
        )

    bmi_val = round(weight / ((height / 100) ** 2), 1) if height else ""
    st.caption(f"Computed BMI: {bmi_val}")

    st.markdown("### 🏃 Lifestyle")
    l1, l2, l3 = st.columns(3)
    with l1:
        activity_level_plan = st.selectbox(
            "Activity Level",
            [
                "Sedentary",
                "Lightly Active",
                "Moderately Active",
                "Very Active",
                "Extremely Active",
            ],
            key="plan_activity_level",
        )
    with l2:
        steps = st.number_input(
            "Daily Steps", min_value=0, value=5000, step=500, key="plan_steps"
        )
    with l3:
        sleep_hours = st.number_input(
            "Sleep Hours", min_value=0.0, max_value=24.0, value=7.0, step=0.5, key="plan_sleep"
        )

    st.markdown("### 🎯 Goals")
    (g1,) = st.columns(1)
    with g1:
        health_goal_plan = st.selectbox(
            "Primary Goal",
            [
                "Weight Loss",
                "Weight Gain",
                "Muscle Gain",
                "Maintenance",
                "General Health",
            ],
            key="plan_goal",
        )

    st.markdown("### 🍽️ Preferences (Optional)")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        allergies = st.text_input(
            "Allergies", placeholder="e.g., peanuts, lactose", key="plan_allergies"
        )
    with p2:
        dietary_prefs = st.text_input(
            "Dietary Preferences", placeholder="e.g., Low-Carb, Vegan", key="plan_dietary"
        )
    with p3:
        cuisine = st.text_input(
            "Preferred Cuisine", placeholder="e.g., Burmese", key="plan_cuisine"
        )
    with p4:
        aversions = st.text_input(
            "Food Aversions", placeholder="e.g., bitter greens", key="plan_aversions"
        )

    st.markdown("### 🏥 Health Metrics (Optional)")
    h1, h2, h3, h4 = st.columns(4)
    with h1:
        chronic = st.text_input(
            "Chronic Disease", placeholder="e.g., None", key="plan_chronic"
        )
    with h2:
        bp = st.text_input("Blood Pressure", placeholder="e.g., Normal", key="plan_bp")
    with h3:
        cholesterol = st.text_input(
            "Cholesterol Level", placeholder="e.g., Normal", key="plan_chol"
        )
    with h4:
        blood_sugar = st.text_input(
            "Blood Sugar Level", placeholder="e.g., Normal", key="plan_bs"
        )

    save_col1, save_col2 = st.columns([1, 3])
    with save_col1:
        save_prefs = st.button("💾 Save Data", width='stretch')
    if save_prefs:
        if not st.session_state.user_data:
            st.error("Please log in to save preferences.")
        else:
            prefs = {
                "Age": age,
                "Gender": gender,
                "Height_cm": height,
                "Weight_kg": weight,
                "BMI": bmi_val,
                "Allergies": allergies or "None",
                "Daily_Steps": int(steps),
                "Sleep_Hours": sleep_hours,
                "Current_Goals": health_goal_plan,
                "Dietary_Preferences": dietary_prefs or "",
                "Exercise_Frequency": activity_level_plan,
                "Preferred_Cuisine": cuisine or "",
                "Food_Aversions": aversions or "",
                "Chronic_Disease": chronic or "",
                "Blood_Pressure": bp or "",
                "Cholesterol_Level": cholesterol or "",
                "Blood_Sugar_Level": blood_sugar or "",
            }
            macros = st.session_state.get("plan_macros")
            if isinstance(macros, dict):
                prefs["Plan_Macros"] = macros
            ok = db_manager.save_user_preferences(
                st.session_state.user_data["id"], prefs
            )
            if ok:
                st.success("Data saved.")
            else:
                st.error("Failed to save preferences.")

    st.divider()

    if st.button("✨ Generate Plan", type="primary"):
        with st.spinner("Generating personalized plan..."):
            try:
                fields = {
                    "Age": age,
                    "Gender": gender,
                    "Height_cm": height,
                    "Weight_kg": weight,
                    "BMI": bmi_val,
                    "Allergies": allergies or "None",
                    "Daily_Steps": int(steps),
                    "Sleep_Hours": sleep_hours,
                    "Current_Goals": health_goal_plan,
                    "Dietary_Preferences": dietary_prefs or "",
                    "Exercise_Frequency": activity_level_plan,
                    "Preferred_Cuisine": cuisine or "",
                    "Food_Aversions": aversions or "",
                    "Chronic_Disease": chronic or "",
                    "Blood_Pressure": bp or "",
                    "Cholesterol_Level": cholesterol or "",
                    "Blood_Sugar_Level": blood_sugar or "",
                }
                plan_json = get_plan_json(fields)
                if isinstance(plan_json, dict) and all(
                    k in plan_json for k in ["calories", "protein_g", "carbs_g", "fats_g", "meals"]
                ):
                    st.success("Plan generated")
                    # st.info("Save this plan to enable personalized answers in Chat.")
                    # if st.button("💾 Save This Plan", key="save_after_plan"):
                    #     if not st.session_state.user_data:
                    #         st.error("Please log in to save preferences.")
                    #     else:
                    #         prefs = {
                    #             "Age": age,
                    #             "Gender": gender,
                    #             "Height_cm": height,
                    #             "Weight_kg": weight,
                    #             "BMI": bmi_val,
                    #             "Allergies": allergies or "None",
                    #             "Daily_Steps": int(steps),
                    #             "Sleep_Hours": sleep_hours,
                    #             "Current_Goals": health_goal_plan,
                    #             "Dietary_Preferences": dietary_prefs or "",
                    #             "Exercise_Frequency": activity_level_plan,
                    #             "Preferred_Cuisine": cuisine or "",
                    #             "Food_Aversions": aversions or "",
                    #             "Chronic_Disease": chronic or "",
                    #             "Blood_Pressure": bp or "",
                    #             "Cholesterol_Level": cholesterol or "",
                    #             "Blood_Sugar_Level": blood_sugar or "",
                    #         }
                    #         macros = st.session_state.get("plan_macros")
                    #         if isinstance(macros, dict):
                    #             prefs["Plan_Macros"] = macros
                    #         ok = db_manager.save_user_preferences(
                    #             st.session_state.user_data["id"], prefs
                    #         )
                    #         if ok:
                    #             st.success("Saved. Your chat will be personalized using this plan.")
                    #         else:
                    #             st.error("Failed to save preferences.")
                    st.markdown("### 📋 Suggested Plan")
                    st.markdown(f"- Calories: {plan_json.get('calories')} kcal")
                    st.markdown(f"- Protein: {plan_json.get('protein_g')} g")
                    st.markdown(f"- Carbs: {plan_json.get('carbs_g')} g")
                    st.markdown(f"- Fats: {plan_json.get('fats_g')} g")
                    st.session_state.plan_macros = {
                        "calories": plan_json.get("calories"),
                        "protein_g": plan_json.get("protein_g"),
                        "carbs_g": plan_json.get("carbs_g"),
                        "fat_g": plan_json.get("fats_g"),
                    }
                    meals = plan_json.get("meals") or {}
                    if isinstance(meals, dict):
                        st.markdown("#### Meals")
                        st.markdown(f"- Breakfast: {meals.get('breakfast','-')}")
                        st.markdown(f"- Lunch: {meals.get('lunch','-')}")
                        st.markdown(f"- Snack: {meals.get('snack','-')}")
                        st.markdown(f"- Dinner: {meals.get('dinner','-')}")
                    notes = plan_json.get("notes")
                    if notes:
                        st.markdown("#### Notes")
                        st.markdown(notes)
                else:
                    st.warning("Model did not return structured JSON. Showing raw output.")
                    st.write(plan_json)
            except Exception as e:
                st.error(
                    f"Plan generation failed: {e}. Ensure MISTRAL_API_KEY is set in your environment."
                )
