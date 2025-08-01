import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random

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
