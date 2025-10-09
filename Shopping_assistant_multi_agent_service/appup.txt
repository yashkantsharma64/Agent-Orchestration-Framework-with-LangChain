# app.py
# Step 1: Import necessary libraries
import uuid
import statistics
import requests
import json
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# --- LLM and LangChain Setup (from your script) ---
from langchain_community.llms import HuggingFacePipeline
from transformers import pipeline as hf_pipeline_fn
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables from .env file

load_dotenv("abh.env")

def create_llm(model_name="gemini-2.5-flash-lite", temperature=0.3):
  """
  Creates and configures a Google Gemini LLM instance.
  """
  # Check if the API key is available
  #if "GOOGLE_API_KEY" not in os.environ:
      #raise ValueError("Google API Key not found. Please set it in your .env file.")'''
  
  # Configure and return the Gemini model
  llm = ChatGoogleGenerativeAI(
      model=model_name,
      temperature=temperature,
      convert_system_message_to_human=True 
  )
  return llm

# Create the new LLM instance
llm = create_llm()

# --- Data Models (from your script) ---
@dataclass
class Product:
    id: str
    title: str
    specs: Dict[str, Any] = field(default_factory=dict)
    prices: Dict[str, float] = field(default_factory=dict)
    reviews: List[Dict[str, Any]] = field(default_factory=list)

    def average_price(self) -> Optional[float]:
        return statistics.mean(self.prices.values()) if self.prices else None

    def average_rating(self) -> Optional[float]:
        if not self.reviews:
            return None
        return statistics.mean([r["rating"] for r in self.reviews])

# --- Session Management (from your script) ---
class SessionMemory:
    """Shared scratchpad for all agents across a user session."""
    def __init__(self):
        self.logs: List[str] = []
        self.products_seen: Dict[str, Product] = {}
        self.rejected_ids: set = set()
        self.query_history: List[str] = []

    def add_log(self, text: str):
        self.logs.append(text)

    def save_products(self, products: List[Product]):
        for p in products:
            if p.id not in self.products_seen:
                self.products_seen[p.id] = p

    def mark_rejected(self, product_title: str):
        product_id_to_reject = None
        for pid, prod in self.products_seen.items():
            if prod.title.lower() == product_title.lower():
                product_id_to_reject = pid
                break
        if product_id_to_reject:
            self.rejected_ids.add(product_id_to_reject)
            self.add_log(f"User rejected product: {product_title}")

    def get_valid_products(self) -> List[Product]:
        return [p for pid, p in self.products_seen.items() if pid not in self.rejected_ids]

# --- Agent Definitions (adapted from your script for API use) ---
class SearchAgent:
    def __init__(self, memory: SessionMemory):
        self.memory = memory

    def run(self, query: str, max_results: int = 5) -> List[Product]:
        self.memory.query_history.append(query)
        url = "https://dummyjson.com/products/search"
        try:
            req = requests.get(url, params={"q": query}, timeout=10)
            req.raise_for_status()
            data = req.json()
        except requests.exceptions.RequestException as e:
            self.memory.add_log(f"SearchAgent API error: {e}")
            return []

        products_data = data.get('products', [])[:max_results]
        products = []
        for p in products_data:
            product = Product(
                id=str(p['id']),
                title=p['title'],
                specs={"category": p.get('category', 'N/A')}
            )
            products.append(product)

        self.memory.save_products(products)
        self.memory.add_log(f"SearchAgent: query='{query}' -> found {[p.title for p in products]}")
        return products

class ProductDetailAgent:
    """Fetches price and reviews for products."""
    def __init__(self, memory: SessionMemory):
        self.memory = memory

    def run(self, products: List[Product]) -> List[Product]:
        for p in products:
            if p.id in self.memory.rejected_ids:
                continue
            # Fetch details only if not already present
            if not p.prices and not p.reviews:
                try:
                    req = requests.get(f"https://dummyjson.com/products/{p.id}", timeout=10)
                    req.raise_for_status()
                    data = req.json()
                    p.prices = {"online": data.get('price', 0)}
                    rating = data.get('rating', 0)
                    p.reviews = [{"rating": round(rating), "text": "Sample review"}]
                except requests.exceptions.RequestException as e:
                    self.memory.add_log(f"DetailAgent API Error for product {p.id}: {e}")
                    p.prices = {}
                    p.reviews = []
        self.memory.save_products(products)
        self.memory.add_log("ProductDetailAgent: prices and reviews fetched from API")
        return products

class CoordinatorAgent:
    def __init__(self, memory: SessionMemory, llm, budget: float):
        self.memory = memory
        self.llm = llm
        self.budget = budget
        self.prompt = PromptTemplate(
            input_variables=["products_info", "budget"],
            template=(
                "You are a helpful shopping assistant. Here are some products:\n\n"
                "{products_info}\n\n"
                "The user's budget is ₹{budget}.\n\n"
                "Analyze these products and recommend the best one. Explain your choice clearly. "
                "Respond in a valid JSON format with three keys: 'recommendation' (the product title), "
                "'reasons' (a list of short bullet points for your choice), and "
                "'explanation' (a brief text explaining why other options were less suitable)."
            )
        )

    def run(self) -> Dict[str, Any]:
        valid_products = self.memory.get_valid_products()
        affordable = [
            p for p in valid_products
            if p.average_price() is not None and p.average_price() <= self.budget
        ]

        if not affordable:
            msg = f"Sorry, no products found within your budget of ₹{self.budget}."
            self.memory.add_log(f"CoordinatorAgent: {msg}")
            return {"recommendation": None, "reasons": [], "explanation": msg}

        products_info_lines = [
            f"- Title: {p.title}, Price: ₹{p.average_price():.2f}, Rating: {p.average_rating():.2f}/5.0"
            for p in affordable
        ]
        products_info = "\n".join(products_info_lines)

        chain = LLMChain(llm=self.llm, prompt=self.prompt)
        decision_text = chain.run(products_info=products_info, budget=str(self.budget))
        self.memory.add_log(f"CoordinatorAgent raw LLM response: {decision_text[:200]}")

        try:
            # Clean the text to ensure it's valid JSON
            start_index = decision_text.find('{')
            end_index = decision_text.rfind('}') + 1
            if start_index != -1 and end_index != -1:
                json_str = decision_text[start_index:end_index]
                parsed = json.loads(json_str)
                return parsed
            raise json.JSONDecodeError("No JSON object found", decision_text, 0)
        except json.JSONDecodeError:
            self.memory.add_log("CoordinatorAgent: Failed to parse LLM response as JSON.")
            return {"recommendation": "Could not decide", "reasons": [], "explanation": "The AI response was not in the correct format."}

# --- Core Pipeline Logic ---
def run_pipeline(session_memory: SessionMemory, budget: float, llm, new_query: Optional[str] = None):
    """Runs the agent pipeline."""
    if new_query:
        search_agent = SearchAgent(session_memory)
        # Search for new products
        new_products = search_agent.run(new_query)
        # Fetch details for the newly found products
        detail_agent = ProductDetailAgent(session_memory)
        detail_agent.run(new_products)

    # Coordinator runs on all non-rejected products seen in the session
    coordinator = CoordinatorAgent(session_memory, llm, budget)
    recommendation = coordinator.run()

    return session_memory.get_valid_products(), recommendation

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Multi-Agent Shopping Assistant API",
    description="An API to power an intelligent shopping assistant.",
    version="1.0.0"
)

LLM_INSTANCE = create_llm()
SESSIONS: Dict[str, SessionMemory] = {}
BUDGETS: Dict[str, float] = {}

# --- API Request and Response Models ---
class StartRequest(BaseModel):
    name: str = Field(..., example="Alex")
    user_query: str = Field(..., example="smartphone")
    budget: float = Field(..., example=25000.0)

class ProductModel(BaseModel):
    id: str
    title: str
    avg_price: Optional[float]
    avg_rating: Optional[float]

class RecommendationModel(BaseModel):
    recommendation: Optional[str]
    reasons: List[str]
    explanation: str

class StartResponse(BaseModel):
    session_id: str
    products: List[ProductModel]
    recommendation: RecommendationModel

class RefineRequest(BaseModel):
    session_id: str
    action: str = Field(..., example="reject", description="'reject', 'show', or 'budget'")
    value: str = Field(..., example="iPhone 9", description="Product title to reject, new search query, or new budget amount")

class RefineResponse(BaseModel):
    products: List[ProductModel]
    recommendation: RecommendationModel
    current_budget: float

# --- API Endpoints ---
@app.post("/start", response_model=StartResponse)
def start_session(request: StartRequest):
    """Starts a new shopping session."""
    session_id = str(uuid.uuid4())
    session_memory = SessionMemory()
    SESSIONS[session_id] = session_memory
    BUDGETS[session_id] = request.budget

    products, recommendation = run_pipeline(session_memory, request.budget, LLM_INSTANCE, new_query=request.user_query)

    response_products = [ProductModel(id=p.id, title=p.title, avg_price=p.average_price(), avg_rating=p.average_rating()) for p in products]

    return StartResponse(
        session_id=session_id,
        products=response_products,
        recommendation=recommendation
    )

@app.post("/refine", response_model=RefineResponse)
def refine_session(request: RefineRequest):
    """Refines an existing shopping session by rejecting an item, searching for more, or changing budget."""
    session_id = request.session_id
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")

    session_memory = SESSIONS[session_id]
    budget = BUDGETS[session_id]
    new_query = None

    if request.action == "reject":
        session_memory.mark_rejected(request.value)
    elif request.action == "show":
        new_query = request.value
    elif request.action == "budget":
        try:
            new_budget = float(request.value)
            if new_budget <= 0:
                raise HTTPException(status_code=400, detail="Budget must be a positive number")
            BUDGETS[session_id] = new_budget
            budget = new_budget
            session_memory.add_log(f"Budget updated to ₹{new_budget}")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid budget value. Must be a number.")
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'reject', 'show', or 'budget'.")

    products, recommendation = run_pipeline(session_memory, budget, LLM_INSTANCE, new_query=new_query)

    response_products = [ProductModel(id=p.id, title=p.title, avg_price=p.average_price(), avg_rating=p.average_rating()) for p in products]

    return RefineResponse(
        products=response_products,
        recommendation=recommendation,
        current_budget=budget
    )