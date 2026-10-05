# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Seed script to populate Firestore with initial recipes."""

import json
import os
from google.cloud import firestore

# IMPORTANT: Hardcoded Project ID string
PROJECT_ID = "qwiklabs-gcp-03-1ff82139de18"
COLLECTION_NAME = "recipes"
LOCAL_FALLBACK_FILE = os.path.join("app", "recipes_data.json")

SEED_RECIPES = [
    {
        "id": "avocado-toast",
        "name": "Avocado & Poached Egg Toast",
        "cuisine": "American",
        "ingredients": [
            "2 slices sourdough bread",
            "1 ripe avocado",
            "2 large eggs",
            "1 tbsp extra virgin olive oil",
            "Salt, black pepper, red pepper flakes",
        ],
        "instructions": "Toast sourdough slices. Mash avocado with olive oil, salt, and pepper. Poach eggs in simmering water for 3 minutes. Spread avocado on toast, top with poached eggs, and sprinkle red pepper flakes.",
        "prep_time_minutes": 10,
        "dietary_tags": ["vegetarian", "breakfast", "quick"],
    },
    {
        "id": "quinoa-buddha-bowl",
        "name": "Mediterranean Quinoa Buddha Bowl",
        "cuisine": "Mediterranean",
        "ingredients": [
            "1 cup cooked quinoa",
            "1/2 cup canned chickpeas, rinsed",
            "1/2 cup cherry tomatoes, halved",
            "1/2 cup cucumber, diced",
            "2 tbsp tahini dressing",
            "1/4 cup kalamata olives",
        ],
        "instructions": "Arrange cooked quinoa in a bowl. Top with sections of chickpeas, cherry tomatoes, cucumber, and olives. Drizzle with creamy tahini dressing before serving.",
        "prep_time_minutes": 15,
        "dietary_tags": ["vegan", "gluten-free", "lunch", "healthy"],
    },
    {
        "id": "lemon-herb-salmon",
        "name": "Lemon Herb Baked Salmon",
        "cuisine": "Seafood",
        "ingredients": [
            "2 fresh salmon fillets",
            "1 tbsp olive oil",
            "1 lemon, sliced",
            "2 cloves garlic, minced",
            "1 tbsp fresh dill and parsley",
            "Salt and black pepper",
        ],
        "instructions": "Preheat oven to 400°F (200°C). Place salmon on a lined baking sheet, rub with olive oil and garlic. Season with salt, pepper, and fresh herbs. Top with lemon slices and bake for 12-15 minutes.",
        "prep_time_minutes": 20,
        "dietary_tags": ["pescatarian", "gluten-free", "low-carb", "dinner"],
    },
    {
        "id": "wild-mushroom-risotto",
        "name": "Creamy Wild Mushroom Risotto",
        "cuisine": "Italian",
        "ingredients": [
            "1 cup Arborio rice",
            "8 oz mixed wild mushrooms, sliced",
            "4 cups warm vegetable broth",
            "1/2 cup dry white wine",
            "1 shallot, finely chopped",
            "1/4 cup grated Parmesan cheese",
            "2 tbsp butter",
        ],
        "instructions": "Sauté mushrooms and shallots in butter until golden. Add Arborio rice and toast 2 minutes. Deglaze with white wine. Gradually add warm broth 1 ladle at a time while stirring until creamy. Stir in Parmesan and serve warm.",
        "prep_time_minutes": 35,
        "dietary_tags": ["vegetarian", "dinner", "classic"],
    },
]


def seed_database():
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")

    # Always write to local seed file for local agent execution
    os.makedirs(os.path.dirname(LOCAL_FALLBACK_FILE), exist_ok=True)
    local_store = {
        item["id"]: {k: v for k, v in item.items() if k != "id"}
        for item in SEED_RECIPES
    }
    with open(LOCAL_FALLBACK_FILE, "w") as f:
        json.dump(local_store, f, indent=2)
    print(f"  ✓ Seeded local recipes store ({LOCAL_FALLBACK_FILE})")

    # Attempt writing to GCP Firestore
    try:
        db = firestore.Client(project=PROJECT_ID)
        collection_ref = db.collection(COLLECTION_NAME)

        for item in SEED_RECIPES:
            doc_id = item["id"]
            doc_data = {k: v for k, v in item.items() if k != "id"}
            collection_ref.document(doc_id).set(doc_data)
            print(f"  ✓ Seeded Firestore document: {item['name']} (ID: {doc_id})")

        print("\n✅ Firestore GCP database successfully seeded!")
    except Exception as e:
        print(f"\n⚠️  Note: Could not write to GCP Cloud Firestore ({type(e).__name__}).")
        print("   Local recipe seed store is active and fully functional for local testing!")


if __name__ == "__main__":
    seed_database()
