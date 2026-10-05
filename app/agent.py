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
import os

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.genai import types

from app.a2ui_utils import a2ui_callback
from app.tools import (
    add_recipe,
    generate_dish_image,
    get_recipe,
    load_memory,
    save_user_memory,
    scale_recipe_ingredients,
    search_public_meals,
    search_recipes,
)

# Load Agent Engine resource name from deployment_metadata.json if present
DEPLOYMENT_METADATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json"
)

PROJECT_ID = "qwiklabs-gcp-03-1ff82139de18"
LOCATION = "us-east1"
agent_engine_resource_name = None
if os.path.exists(DEPLOYMENT_METADATA_PATH):
    try:
        with open(DEPLOYMENT_METADATA_PATH, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception:
        pass

# Extract Agent Engine ID for Memory Bank service
AGENT_ENGINE_ID = (
    agent_engine_resource_name.split("/")[-1]
    if agent_engine_resource_name
    else "3351294948786831360"
)


def memory_service_builder():
    """Builds VertexAiMemoryBankService for Memory Bank persistence on deployment."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location=LOCATION,
        agent_engine_id=AGENT_ENGINE_ID,
    )


code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)

# Build A2UI v0.8 system prompt using BasicCatalog
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are an expert Personal Chef AI assistant. "
        "Help users discover, customize, scale, and prepare delicious meals. "
        "Always remember and respect user allergies, dietary restrictions, and food preferences across sessions. "
        "Whenever a user states an allergy, dietary restriction, or preference (e.g. 'I am allergic to peanuts', 'I am vegan'), "
        "immediately call `save_user_memory` to store it permanently in their Memory Bank. "
        "At the start of a conversation or before recommending recipes, call `load_memory` to check for stored user allergies and preferences. "
        "Ensure all future recipe recommendations and meal suggestions strictly avoid those allergens. "
        "Use your database tools (`search_recipes`, `get_recipe`, `add_recipe`) "
        "to search for existing user recipes, fetch detailed cooking instructions, or save new recipes. "
        "Use `search_public_meals` to search global recipes and meal ideas from the free public TheMealDB database. "
        "Use `scale_recipe_ingredients` whenever a user asks to scale ingredient "
        "quantities for a specific number of servings. "
        "Use `generate_dish_image` whenever a user asks for a visual image or photo of a dish/recipe. "
        "You have Python code execution enabled via AgentEngineSandboxCodeExecutor. "
        "When performing calculations or writing Python code, enclose the code in ```python ... ``` code blocks. "
        "Do NOT call a function named google:python_interpreter."
    ),
    workflow_description="Analyze the request, call necessary tools, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        search_recipes,
        get_recipe,
        add_recipe,
        scale_recipe_ingredients,
        search_public_meals,
        generate_dish_image,
        load_memory,
        save_user_memory,
    ],
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
