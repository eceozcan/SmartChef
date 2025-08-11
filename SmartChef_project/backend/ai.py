import requests  # type: ignore
import re
from fractions import Fraction
from collections import defaultdict
from datetime import datetime

# Normalize and singularize ingredient names
def normalize(ingredient):
    ingredient = ingredient.strip().lower()
    if ingredient.endswith("s"):
        ingredient = ingredient[:-1]
    return ingredient

# Function to separate quantity and unit
def parse_measure(measure):
    measure = measure.strip().lower()
    fraction_match = re.match(r"(\d+/\d+)\s*(.*)", measure)
    if fraction_match:
        quantity_str, unit = fraction_match.groups()
        return quantity_str, unit if unit else ""
    match = re.match(r"(\d+)\s*(.*)", measure)
    if match:
        quantity, unit = match.groups()
        return quantity, unit if unit else ""
    return "0", ""

# Check for ingredient matches
def is_related_ingredient(user_ing, recipe_ing):
    user_ing = normalize(user_ing)
    recipe_ing = normalize(recipe_ing)
    return user_ing in recipe_ing or recipe_ing in user_ing

# Get recipes by ingredient from TheMealDB API
def get_recipes_by_ingredient(ingredient):
    url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={ingredient}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"API request failed for '{ingredient}': {response.status_code}")
        return []
    data = response.json()
    meals = data.get("meals")
    return meals if meals is not None else []

# Strictly filter recipes that actually contain the target ingredient
def filter_recipes_by_strict_ingredient(recipes, target_ingredient):
    filtered = []
    for recipe in recipes:
        recipe_id = recipe["idMeal"]
        ingredients, _, _ = get_recipe_details(recipe_id)
        for ing in ingredients:
            if is_related_ingredient(ing, target_ingredient):
                filtered.append(recipe)
                break
    return filtered

# Get recipe details (ingredients, instructions, tags)
def get_recipe_details(recipe_id):
    url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={recipe_id}"
    response = requests.get(url)
    data = response.json()
    if data.get("meals"):
        meal = data["meals"][0]
        ingredients = {}
        for i in range(1, 21):
            ing = meal.get(f"strIngredient{i}")
            measure = meal.get(f"strMeasure{i}")
            if ing and measure:
                quantity, unit = parse_measure(measure)
                ingredients[normalize(ing)] = (quantity, unit)
        instructions = meal.get("strInstructions", "No description available.")
        tags = meal.get("strTags", "").split(",") if meal.get("strTags") else []
        tags = [tag.strip().lower() for tag in tags]
        return ingredients, instructions, tags
    return {}, "No description available.", []

# Get recipe name
def get_recipe_name(recipe_id):
    url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={recipe_id}"
    response = requests.get(url)
    data = response.json()
    if data.get("meals"):
        return data["meals"][0]["strMeal"]
    return "Unknown Recipe"

# Collect all available tags
def get_all_tags():
    tags = set()
    url = "https://www.themealdb.com/api/json/v1/1/list.php?c=list"
    response = requests.get(url)
    if response.status_code != 200:
        print("Failed to fetch categories. Please check your internet connection.")
        return tags
    
    data = response.json()
    categories = data.get("meals", [])
    if not categories:
        print("No categories found.")
        return tags
    
    for category in categories:
        category_name = category["strCategory"]
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php?c={category_name}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to fetch recipes for category '{category_name}'.")
            continue
        
        data = response.json()
        meals = data.get("meals", [])
        if not meals:
            continue
        
        for meal in meals:
            recipe_id = meal["idMeal"]
            url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={recipe_id}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get("meals"):
                    meal_data = data["meals"][0]
                    if meal_data.get("strTags"):
                        meal_tags = meal_data["strTags"].split(",")
                        tags.update([tag.strip().lower() for tag in meal_tags])
    
    return sorted(list(tags))

# Main function
def main():
    # Get all available tags
    print("Loading tags...")
    all_tags = get_all_tags()
    if not all_tags:
        print("Failed to load tags. Please check your internet connection.")
        return
    print("Available tags:", ", ".join(all_tags))

    # User selects tags (multiple tags comma-separated or 'close')
    selected_tags = []
    while True:
        selected_tags_input = input("Enter tags separated by commas (e.g., Dessert, Vegetarian) or type 'close' to skip: ").strip().lower()
        if selected_tags_input == "close":
            break
        if selected_tags_input:
            selected_tags = [tag.strip() for tag in selected_tags_input.split(",")]
            invalid_tags = [tag for tag in selected_tags if tag not in all_tags]
            if invalid_tags:
                print(f"Invalid tags: {', '.join(invalid_tags)}. Please select from available tags.")
            else:
                break

    # Get user's ingredients
    user_ingredients = {}
    print("\nEnter ingredients in 'quantity ingredient, DAY-MONTH-YEAR' format (e.g., '1 onion, 10-03-2025'). Type 'close' to finish.")
    while True:
        ingredient_input = input("Enter ingredient: ").strip().lower()
        if ingredient_input == "close":
            break
        match = re.match(r"(\d+/\d+|\d+)\s*(\w*)\s+([^,]+),\s*(\d{2}-\d{2}-\d{4})", ingredient_input)
        if match:
            quantity, unit, name, expiry_date = match.groups()
            try:
                datetime.strptime(expiry_date, "%d-%m-%Y")
            except ValueError:
                print("Invalid date format! Please use DAY-MONTH-YEAR format (e.g., 10-03-2025).")
                continue
            normalized_name = normalize(name.strip())
            user_ingredients[normalized_name] = (quantity, unit if unit else "", expiry_date)
        else:
            print("Invalid input! Please use 'quantity ingredient, DAY-MONTH-YEAR' format (e.g., '1 onion, 10-03-2025').")

    if not user_ingredients:
        print("No ingredients entered!")
        return

    # Find recipes matching the ingredients
    recipe_matches = defaultdict(set)
    for ingredient in user_ingredients.keys():
        recipes = get_recipes_by_ingredient(ingredient)
        for recipe in recipes:
            recipe_id = recipe["idMeal"]
            recipe_matches[recipe_id].add(ingredient)

    # Filter recipes with at least 2 matching ingredients
    min_matches = 2
    filtered_recipes = {k: v for k, v in recipe_matches.items() if len(v) >= min_matches}

    if not filtered_recipes:
        print("No recipes found with at least 2 matching ingredients.")
        return

    # Sort ingredients by expiration date
    sorted_ingredients = sorted(
        user_ingredients.items(),
        key=lambda x: datetime.strptime(x[1][2], "%d-%m-%Y")
    )

    # Sort recipes by expiration groups
    sorted_recipes = []
    used_recipe_ids = set()  # To prevent duplicates
    for ing_name, (_, _, expiry_date) in sorted_ingredients:
        expiry_datetime = datetime.strptime(expiry_date, "%d-%m-%Y")
        # Get recipes containing this ingredient
        ingredient_recipes = []
        for recipe_id in filtered_recipes.keys():
            if ing_name in recipe_matches[recipe_id] and recipe_id not in used_recipe_ids:
                # Calculate tag matches
                _, _, tags = get_recipe_details(recipe_id)
                match_count = len([tag for tag in selected_tags if tag in tags]) if selected_tags else 0
                ingredient_recipes.append((recipe_id, expiry_datetime, match_count))
        
        # Sort by tag matches and recipe name
        ingredient_recipes.sort(key=lambda x: (-x[2], get_recipe_name(x[0])))
        
        # Add recipes and mark as used
        for recipe_id, expiry, match_count in ingredient_recipes:
            sorted_recipes.append((recipe_id, expiry, match_count))
            used_recipe_ids.add(recipe_id)

    if not sorted_recipes:
        print("No suitable recipes found.")
        return

    # Display found recipes
    print("\nFound recipes:")
    for idx, (recipe_id, _, _) in enumerate(sorted_recipes, start=1):
        print(f"{idx}. {get_recipe_name(recipe_id)}")

    # User selects a recipe
    try:
        selection = int(input("\nEnter the number of the recipe you want to select: "))
        if selection < 1 or selection > len(sorted_recipes):
            print("Invalid number!")
            return
    except ValueError:
        print("Please enter a valid number!")
        return

    selected_recipe_id = sorted_recipes[selection - 1][0]

    # Get recipe details
    recipe_ingredients, instructions, _ = get_recipe_details(selected_recipe_id)

    # Calculate missing ingredients
    missing_ingredients = []
    for ing, (req_quantity, req_unit) in recipe_ingredients.items():
        matching_ingredients = [user_ing for user_ing in user_ingredients.keys() if is_related_ingredient(user_ing, ing)]
        if matching_ingredients:
            user_ing = matching_ingredients[0]
            user_quantity, user_unit, expiry_date = user_ingredients[user_ing]
            req_qty_num = float(Fraction(req_quantity))
            user_qty_num = float(Fraction(user_quantity))
            if user_qty_num < req_qty_num:
                if user_unit == req_unit:
                    missing_qty = req_qty_num - user_qty_num
                    missing_ingredients.append(f"{missing_qty} {req_unit} {ing} (You have: {user_quantity} {user_unit})")
                else:
                    missing_ingredients.append(f"{req_quantity} {req_unit} {ing} (You have: {user_quantity} {user_unit} {user_ing})")
        else:
            missing_ingredients.append(f"{req_quantity} {req_unit} {ing}")

    # Print results
    print(f"\nSelected recipe: {get_recipe_name(selected_recipe_id)}\n")
    print("Recipe instructions:")
    print(instructions)
    print("\nMissing ingredients:")
    if not missing_ingredients:
        print("You have all ingredients needed for this recipe!")
    else:
        print(", \n".join(missing_ingredients))
    
    print("\n\n")

# Run the code
# if __name__ == "__main__":
#     main()