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

import json
import urllib.parse
import urllib.request
from typing import Any

from google.adk.memory.memory_entry import MemoryEntry
from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService
from google.adk.tools import ToolContext
from google.cloud import firestore
from google.genai import Client, types

# Hardcoded Firestore Project ID as directed by guidelines
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-1ff82139de18"
STORAGE_BUCKET_NAME = "personal-chef-media-qwiklabs-gcp-03-1ff82139de18"

# Initialize Firestore Client
db = firestore.Client(project=FIRESTORE_PROJECT_ID)


def search_recipes(query: str) -> list[dict[str, Any]]:
    """Searches user recipes stored in Firestore database by matching recipe title or tags.

    Args:
        query: The search term or keyword to find recipes.

    Returns:
        List of matching recipe dictionaries with id, title, description, prep_time, cook_time, servings, tags.
    """
    recipes_ref = db.collection("recipes")
    docs = recipes_ref.stream()

    results = []
    query_lower = query.lower()

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id

        title = data.get("title", "").lower()
        description = data.get("description", "").lower()
        tags = [t.lower() for t in data.get("tags", [])]

        if query_lower in title or query_lower in description or any(query_lower in t for t in tags):
            # Omit full steps/ingredients in summary search results
            results.append({
                "id": data["id"],
                "title": data.get("title"),
                "description": data.get("description"),
                "prep_time": data.get("prep_time"),
                "cook_time": data.get("cook_time"),
                "servings": data.get("servings"),
                "tags": data.get("tags", []),
            })

    return results


def get_recipe(recipe_id: str) -> dict[str, Any]:
    """Retrieves full details for a specific recipe from Firestore by ID.

    Args:
        recipe_id: The unique document ID of the recipe.

    Returns:
        Dictionary containing title, description, ingredients, steps, prep_time, cook_time, servings, tags.
    """
    doc_ref = db.collection("recipes").document(recipe_id)
    doc = doc_ref.get()

    if not doc.exists:
        return {"error": f"Recipe with ID '{recipe_id}' not found."}

    data = doc.to_dict()
    data["id"] = doc.id
    return data


def add_recipe(
    title: str,
    description: str,
    ingredients: list[dict[str, Any]],
    steps: list[str],
    prep_time: str,
    cook_time: str,
    servings: int,
    tags: list[str],
) -> dict[str, Any]:
    """Saves a new user-customized recipe to the Firestore database.

    Args:
        title: Title of the recipe.
        description: Brief summary of the dish.
        ingredients: List of ingredient objects, e.g. [{"name": "salt", "quantity": 1, "unit": "tsp"}].
        steps: List of step-by-step cooking instruction strings.
        prep_time: Preparation time (e.g., '15 mins').
        cook_time: Cooking time (e.g., '30 mins').
        servings: Default number of servings.
        tags: List of descriptive tags (e.g., ['dinner', 'easy']).

    Returns:
        Dictionary with confirmation status and new recipe ID.
    """
    new_doc = db.collection("recipes").document()
    recipe_data = {
        "title": title,
        "description": description,
        "ingredients": ingredients,
        "steps": steps,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "servings": servings,
        "tags": tags,
    }
    new_doc.set(recipe_data)

    return {
        "status": "success",
        "message": f"Recipe '{title}' saved successfully.",
        "recipe_id": new_doc.id,
    }


def scale_recipe_ingredients(
    ingredients: list[dict[str, Any]], base_servings: int, target_servings: int
) -> dict[str, Any]:
    """Calculates scaled ingredient quantities for a recipe based on target servings.

    Args:
        ingredients: List of ingredient dicts with keys 'name', 'quantity' (float/int), 'unit' (str).
        base_servings: The original number of servings the recipe yields (must be > 0).
        target_servings: The desired number of servings to scale to (must be > 0).

    Returns:
        Dictionary containing scaled ingredients list and scaling factor ratio.
    """
    if base_servings <= 0 or target_servings <= 0:
        return {"error": "Base servings and target servings must be positive integers greater than 0."}

    scale_factor = target_servings / base_servings
    scaled_ingredients = []

    for ing in ingredients:
        name = ing.get("name", "Unknown ingredient")
        unit = ing.get("unit", "")
        qty = ing.get("quantity")

        if isinstance(qty, (int, float)):
            scaled_qty = round(qty * scale_factor, 2)
            # Format cleanly if whole number
            if scaled_qty.is_integer():
                scaled_qty = int(scaled_qty)
        else:
            scaled_qty = qty

        scaled_ingredients.append({
            "name": name,
            "quantity": scaled_qty,
            "unit": unit,
        })

    return {
        "base_servings": base_servings,
        "target_servings": target_servings,
        "scale_factor": round(scale_factor, 2),
        "ingredients": scaled_ingredients,
    }


def search_public_meals(query: str) -> dict[str, Any]:
    """Searches the free public TheMealDB database for meal recipes by name or main ingredient.

    Args:
        query: The meal or ingredient name to search for (e.g. 'chicken', 'pasta', 'tacos').

    Returns:
        Dictionary with matching public meal items including name, category, cuisine area, instructions, and ingredients.
    """
    encoded_query = urllib.parse.quote(query.strip())
    url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={encoded_query}"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
            meals = payload.get("meals")

            if not meals:
                return {"message": f"No public meals found matching '{query}'."}

            formatted_meals = []
            for meal in meals[:5]:  # Return top 5 results
                # Build ingredients list from TheMealDB strIngredient1..20 & strMeasure1..20
                ingredients = []
                for i in range(1, 21):
                    ing = meal.get(f"strIngredient{i}")
                    measure = meal.get(f"strMeasure{i}")
                    if ing and ing.strip():
                        ingredients.append(
                            f"{measure.strip()} {ing.strip()}".strip() if measure else ing.strip()
                        )

                formatted_meals.append({
                    "id": meal.get("idMeal"),
                    "name": meal.get("strMeal"),
                    "category": meal.get("strCategory"),
                    "area": meal.get("strArea"),
                    "instructions": meal.get("strInstructions"),
                    "ingredients": ingredients,
                    "thumbnail_url": meal.get("strMealThumb"),
                })

            return {"query": query, "count": len(formatted_meals), "meals": formatted_meals}

    except Exception as e:
        return {"error": f"Failed to fetch public meals from TheMealDB API: {str(e)}"}


def generate_dish_image(
    prompt: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Generates a high-quality visual image/photo of a dish using Gemini 3.1 Flash Lite Image model,
    saves it to Playground Artifacts, and uploads it to a public Cloud Storage bucket.

    Args:
        prompt: Detailed visual prompt describing the dish or meal image to generate.
        tool_context: Tool context automatically provided by ADK framework.

    Returns:
        Dictionary containing image metadata and the public https URL.
    """
    client = Client(
        vertexai=True,
        project=FIRESTORE_PROJECT_ID,
        location="global",
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
    )

    image_bytes = None
    mime_type = "image/png"

    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

    if not image_bytes:
        return {"error": "Failed to generate image bytes from Gemini image model."}

    # 1. Save artifact for ADK Playground visibility
    filename = "generated_dish.png"
    part_artifact = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    tool_context.save_artifact(filename=filename, artifact=part_artifact)

    # 2. Upload directly to public Cloud Storage bucket
    storage_client = firestore.storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(STORAGE_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{STORAGE_BUCKET_NAME}/{filename}"

    return {
        "status": "success",
        "message": f"Image generated for '{prompt}'.",
        "artifact_filename": filename,
        "public_image_url": public_url,
    }


_memory_bank_service = VertexAiMemoryBankService(
    project="qwiklabs-gcp-03-1ff82139de18",
    location="us-east1",
    agent_engine_id="3351294948786831360",
)


async def load_memory(
    query: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Loads long-term user memories, allergies, and preferences from the Memory Bank.

    Args:
        query: Query string to search for stored user memories (e.g. 'user allergies', 'dietary preferences').
        tool_context: Tool context automatically passed by ADK.

    Returns:
        Dictionary containing list of matched user memories.
    """
    try:
        res = await tool_context.search_memory(query)
        memories = [m.model_dump(mode="json") if hasattr(m, "model_dump") else str(m) for m in res.memories]
        return {"memories": memories}
    except Exception:
        try:
            res = await _memory_bank_service.search_memory(
                app_name=getattr(tool_context, "app_name", "app"),
                user_id=getattr(tool_context, "user_id", "web-user"),
                query=query,
            )
            memories = [m.model_dump(mode="json") if hasattr(m, "model_dump") else str(m) for m in res.memories]
            return {"memories": memories}
        except Exception as e:
            return {"memories": [], "message": f"No stored memories found ({e})"}


async def save_user_memory(
    fact: str,
    tool_context: ToolContext,
) -> str:
    """Saves an important fact, allergy, or dietary preference about the user to their long-term Memory Bank.

    Args:
        fact: Clear statement or fact about the user to remember (e.g. 'User is allergic to peanuts', 'User is vegan').
        tool_context: Tool context automatically passed by ADK framework.

    Returns:
        Confirmation message that the fact has been saved to Memory Bank.
    """
    memory_entry = MemoryEntry(
        content=types.Content(
            parts=[types.Part.from_text(text=fact)]
        )
    )
    try:
        await tool_context.add_memory(memories=[memory_entry])
    except Exception:
        try:
            await _memory_bank_service.add_memory(
                app_name=getattr(tool_context, "app_name", "app"),
                user_id=getattr(tool_context, "user_id", "web-user"),
                memories=[memory_entry],
            )
        except Exception as e:
            return f"Failed to save memory: {e}"
    return f"Successfully saved to user's long-term Memory Bank: '{fact}'"
