# frontend.py
import streamlit as st
import requests
from typing import List, Dict, Any

# --- Configuration ---
API_URL = "http://127.0.0.1:8000"

# --- Helper Functions ---
def start_new_session(name: str, query: str, budget: float):
    """Contacts the backend to start a new session."""
    try:
        response = requests.post(
            f"{API_URL}/start",
            json={"name": name, "user_query": query, "budget": budget}
        )
        response.raise_for_status()
        data = response.json()
        st.session_state.session_id = data['session_id']
        st.session_state.products = data['products']
        st.session_state.recommendation = data['recommendation']
        st.session_state.current_budget = budget
        st.session_state.error = None
    except requests.exceptions.RequestException as e:
        st.session_state.error = f"Could not connect to the backend: {e}"
        st.error(st.session_state.error)

def refine_current_session(action: str, value: str):
    """Contacts the backend to refine the current session."""
    if 'session_id' not in st.session_state:
        st.error("No active session. Please start a new one.")
        return
    try:
        response = requests.post(
            f"{API_URL}/refine",
            json={"session_id": st.session_state.session_id, "action": action, "value": value}
        )
        response.raise_for_status()
        data = response.json()
        st.session_state.products = data['products']
        st.session_state.recommendation = data['recommendation']
        st.session_state.current_budget = data['current_budget']
        st.session_state.error = None
    except requests.exceptions.RequestException as e:
        st.session_state.error = f"Could not connect to the backend: {e}"
        st.error(st.session_state.error)

# --- UI Rendering Functions ---
def display_recommendation(recommendation: Dict[str, Any]):
    """Displays the AI's recommendation."""
    st.subheader("🤖 AI Recommendation")
    rec_product = recommendation.get('recommendation')
    if rec_product:
        st.success(f"**Best Choice:** {rec_product}")
        reasons = recommendation.get('reasons', [])
        if reasons:
            st.markdown("**Why?:**")
            for reason in reasons:
                st.markdown(f"- {reason}")
        explanation = recommendation.get('explanation')
        if explanation:
            st.info(f"**Analysis:** {explanation}")
    else:
        st.warning(recommendation.get('explanation', "No recommendation available."))

def display_products(products: List[Dict[str, Any]]):
    """Displays the list of suggested products."""
    st.subheader("🛒 Product Suggestions")
    if not products:
        st.write("No products to display.")
        return []

    for p in products:
        price = f"₹{p['avg_price']:.2f}" if p['avg_price'] is not None else "N/A"
        rating = f"{p['avg_rating']:.1f}/5.0" if p['avg_rating'] is not None else "N/A"
        st.markdown(f"**{p['title']}** | Price: {price} | Rating: {rating}")
    return [p['title'] for p in products]


# --- Main Application Logic ---
st.set_page_config(page_title="Shopping Assistant", layout="centered")
st.title("🛍️ Multi-Agent Shopping Assistant")

# --- Initial Input Form ---
if 'session_id' not in st.session_state:
    st.write("Welcome! Let's find the perfect product for you.")
    with st.form("start_form"):
        name = st.text_input("What is your name?", "Guest")
        user_query = st.text_input("What product are you looking for?", "laptop")
        budget = st.number_input("What is your budget (₹)?", min_value=0.0, value=50000.0, step=1000.0)
        submitted = st.form_submit_button("Start Shopping")
        if submitted:
            with st.spinner("Assistant is thinking..."):
                start_new_session(name, user_query, budget)
                st.rerun()

# --- Interactive Session View ---
else:
    st.sidebar.header("Session Active")
    
    # Display current budget in sidebar
    if 'current_budget' in st.session_state:
        st.sidebar.metric("Current Budget", f"₹{st.session_state.current_budget:,.2f}")
    
    if st.sidebar.button("End Session & Start New"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # Display results
    display_recommendation(st.session_state.recommendation)
    product_titles = display_products(st.session_state.products)
    st.markdown("---")

    # Display refinement options
    st.header("Refine Your Search")

    # 1. Reject a product
    with st.expander("❌ Reject a Product"):
        if product_titles:
            product_to_reject = st.selectbox(
                "Select a product you don't like:",
                options=product_titles,
                key="rejection_box"
            )
            if st.button("Reject this Product"):
                with st.spinner("Updating recommendation..."):
                    refine_current_session(action="reject", value=product_to_reject)
                    st.rerun()
        else:
            st.write("No products to reject.")

    # 2. Add a new search
    with st.expander("➕ Search for Something Else"):
        new_query = st.text_input("Enter a new product search:", key="new_query_input")
        if st.button("Search for this"):
            if new_query:
                with st.spinner(f"Searching for '{new_query}'..."):
                    refine_current_session(action="show", value=new_query)
                    st.rerun()
            else:
                st.warning("Please enter a search query.")

    # 3. Change budget - NEW FEATURE
    with st.expander("💰 Change Your Budget"):
        st.write(f"**Current Budget:** ₹{st.session_state.current_budget:,.2f}")
        new_budget = st.number_input(
            "Enter your new budget (₹):",
            min_value=0.0,
            value=st.session_state.current_budget,
            step=1000.0,
            key="new_budget_input"
        )
        if st.button("Update Budget"):
            if new_budget != st.session_state.current_budget:
                with st.spinner(f"Updating budget to ₹{new_budget:,.2f}..."):
                    refine_current_session(action="budget", value=str(new_budget))
                    st.success(f"Budget updated to ₹{new_budget:,.2f}!")
                    st.rerun()
            else:
                st.info("New budget is the same as current budget.")