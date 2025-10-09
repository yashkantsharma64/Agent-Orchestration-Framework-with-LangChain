# app.py
import streamlit as st
import statistics
import requests
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import os

# --- LLM and LangChain Setup ---
# Using Google's Gemini model for better performance
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

# Use Streamlit's caching to load the model only once
@st.cache_resource
def create_llm(model_name="gemini-2.5-flash-lite", temperature=0.4):
    """
    Creates and configures a Google Gemini LLM instance using the API key
    from Streamlit's secrets management.
    """
    # Access the secret API key
    google_api_key = st.secrets.get("GOOGLE_API_KEY")

    if not google_api_key:
        st.error("Google API Key not found. Please add it to your Streamlit secrets.")
        st.stop()
        
    # Configure and return the Gemini model
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=google_api_key,
        convert_system_message_to_human=True
    )
    return llm

LLM_INSTANCE = create_llm()

# --- Data Models and Agent Logic (Merged from backend) ---

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
        return statistics.mean([r["rating"] for r in self.reviews]) if self.reviews else None

class SessionMemory:
    """Shared scratchpad for all agents across a user session."""
    def __init__(self):
        self.products_seen: Dict[str, Product] = {}
        self.rejected_ids: set = set()

    def save_products(self, products: List[Product]):
        for p in products:
            if p.id not in self.products_seen:
                self.products_seen[p.id] = p

    def mark_rejected(self, product_title: str):
        product_id_to_reject = next((pid for pid, prod in self.products_seen.items() if prod.title.lower() == product_title.lower()), None)
        if product_id_to_reject:
            self.rejected_ids.add(product_id_to_reject)

    def get_valid_products(self) -> List[Product]:
        return [p for pid, p in self.products_seen.items() if pid not in self.rejected_ids]

class SearchAgent:
    def __init__(self, memory: SessionMemory):
        self.memory = memory

    def run(self, query: str, max_results: int = 5) -> List[Product]:
        url = "https://dummyjson.com/products/search"
        try:
            req = requests.get(url, params={"q": query}, timeout=10)
            req.raise_for_status()
            data = req.json()
        except requests.exceptions.RequestException:
            return []

        products_data = data.get('products', [])[:max_results]
        products = [Product(id=str(p['id']), title=p['title'], specs={"category": p.get('category', 'N/A')}) for p in products_data]
        self.memory.save_products(products)
        return products

class ProductDetailAgent:
    def __init__(self, memory: SessionMemory):
        self.memory = memory

    def run(self, products: List[Product]):
        for p in products:
            if p.id in self.memory.rejected_ids or p.prices:
                continue
            try:
                req = requests.get(f"https://dummyjson.com/products/{p.id}", timeout=10)
                req.raise_for_status()
                data = req.json()
                p.prices = {"online": data.get('price', 0)}
                p.reviews = [{"rating": round(data.get('rating', 0)), "text": "Sample review"}]
            except requests.exceptions.RequestException:
                pass # Silently fail if a single product detail fetch fails
        self.memory.save_products(products)

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
                "Recommend the best product and explain your choice. "
                "Respond in a valid JSON format with keys: 'recommendation' (product title), "
                "'reasons' (a list of short bullet points), and 'explanation'."
            )
        )

    def run(self) -> Dict[str, Any]:
        valid_products = self.memory.get_valid_products()
        affordable = [p for p in valid_products if p.average_price() and p.average_price() <= self.budget]

        if not affordable:
            return {"recommendation": None, "reasons": [], "explanation": f"Sorry, no products found within your budget of ₹{self.budget}."}

        products_info = "\n".join([f"- {p.title} | Price: ₹{p.average_price():.2f} | Rating: {p.average_rating():.2f}" for p in affordable])
        
        chain = LLMChain(llm=self.llm, prompt=self.prompt)
        decision_text = chain.run(products_info=products_info, budget=str(self.budget))
        
        try:
            start_index = decision_text.find('{')
            end_index = decision_text.rfind('}') + 1
            return json.loads(decision_text[start_index:end_index])
        except (json.JSONDecodeError, IndexError):
            return {"recommendation": "Could not decide", "reasons": [], "explanation": "The AI response was not formatted correctly."}

def run_pipeline(session_memory: SessionMemory, budget: float, new_query: Optional[str] = None):
    if new_query:
        search_agent = SearchAgent(session_memory)
        new_products = search_agent.run(new_query)
        detail_agent = ProductDetailAgent(session_memory)
        detail_agent.run(new_products)

    coordinator = CoordinatorAgent(session_memory, LLM_INSTANCE, budget)
    recommendation = coordinator.run()
    return session_memory.get_valid_products(), recommendation

# --- Streamlit UI (Frontend) ---

st.set_page_config(page_title="Shopping Assistant", layout="centered")
st.title("🛍️ AI-Powered Shopping Assistant")

# Initialize session state
if 'session_memory' not in st.session_state:
    st.session_state.session_memory = SessionMemory()
    st.session_state.products = []
    st.session_state.recommendation = {}
    st.session_state.started = False
    st.session_state.current_budget = 50000.0

# --- UI Rendering Functions ---
def display_recommendation(recommendation: Dict[str, Any]):
    st.subheader("🤖 AI Recommendation")
    rec_product = recommendation.get('recommendation')
    if rec_product and "Could not decide" not in rec_product:
        st.success(f"**Best Choice:** {rec_product}")
        if reasons := recommendation.get('reasons', []):
            st.markdown("**Why?:**")
            for reason in reasons: st.markdown(f"- {reason}")
        if explanation := recommendation.get('explanation'):
            st.info(f"**Analysis:** {explanation}")
    else:
        st.warning(recommendation.get('explanation', "No recommendation available."))

def display_products(products: List[Product]):
    st.subheader("🛒 Product Suggestions")
    if not products:
        st.write("No products to display.")
        return []
    
    product_titles = [p.title for p in products]
    for p in products:
        price = f"₹{p.average_price():,.2f}" if p.average_price() is not None else "N/A"
        rating = f"{p.average_rating():.1f}/5.0" if p.average_rating() is not None else "N/A"
        st.markdown(f"**{p.title}** | Price: {price} | Rating: {rating}")
    return product_titles

# --- Main Application Logic ---

if not st.session_state.started:
    st.write("Welcome! Let's find the perfect product for you.")
    with st.form("start_form"):
        name = st.text_input("What is your name?", "Guest")
        user_query = st.text_input("What product are you looking for?", "smartphone")
        budget = st.number_input("What is your budget (₹)?", min_value=0.0, value=st.session_state.current_budget, step=1000.0)
        submitted = st.form_submit_button("Start Shopping")
        if submitted:
            with st.spinner("Assistant is thinking..."):
                st.session_state.current_budget = budget
                products, recommendation = run_pipeline(st.session_state.session_memory, budget, new_query=user_query)
                st.session_state.products = products
                st.session_state.recommendation = recommendation
                st.session_state.started = True
                st.rerun()
else:
    # This block runs after the initial form is submitted
    st.sidebar.header("Session Active")
    st.sidebar.metric("Current Budget", f"₹{st.session_state.current_budget:,.2f}")
    if st.sidebar.button("End Session & Start New"):
        st.session_state.clear()
        st.rerun()

    display_recommendation(st.session_state.recommendation)
    product_titles = display_products(st.session_state.products)
    st.markdown("---")
    st.header("Refine Your Search")

    with st.expander("💰 Change Your Budget"):
        new_budget = st.number_input("Enter your new budget (₹):", min_value=0.0, value=st.session_state.current_budget, step=1000.0, key="new_budget_input")
        if st.button("Update Budget"):
            with st.spinner(f"Updating recommendation for new budget..."):
                st.session_state.current_budget = new_budget
                products, recommendation = run_pipeline(st.session_state.session_memory, new_budget)
                st.session_state.products = products
                st.session_state.recommendation = recommendation
                st.rerun()

    with st.expander("❌ Reject a Product"):
        if product_titles:
            product_to_reject = st.selectbox("Select a product you don't like:", options=product_titles, key="rejection_box")
            if st.button("Reject this Product"):
                with st.spinner("Updating recommendation..."):
                    st.session_state.session_memory.mark_rejected(product_to_reject)
                    products, recommendation = run_pipeline(st.session_state.session_memory, st.session_state.current_budget)
                    st.session_state.products = products
                    st.session_state.recommendation = recommendation
                    st.rerun()
    
    with st.expander("➕ Search for Something Else"):
        new_query = st.text_input("Enter a new product search:", key="new_query_input")
        if st.button("Search for this"):
            if new_query:
                with st.spinner(f"Searching for '{new_query}'..."):
                    products, recommendation = run_pipeline(st.session_state.session_memory, st.session_state.current_budget, new_query=new_query)
                    st.session_state.products = products
                    st.session_state.recommendation = recommendation
                    st.rerun()

