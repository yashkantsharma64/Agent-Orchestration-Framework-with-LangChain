import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Multi AI Agent Services Hub",
    page_icon="🤖",
    layout="wide"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 3.5rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(90deg, #FF6B6B 0%, #4ECDC4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
    }
    .card-link {
        text-decoration: none !important;
        color: inherit;
        display: block;
    }
    .card-link:hover {
        text-decoration: none !important;
    }
    .card-container {
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        text-align: center;
        height: 300px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        margin: 1rem;
        cursor: pointer;
        position: relative;
        text-decoration: none !important;
    }
    .card-container:hover {
        transform: translateY(-10px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.2);
        text-decoration: none !important;
    }
    .card-1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    .card-2 {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
    }
    .emoji {
        font-size: 4rem;
        margin-bottom: 1rem;
        text-decoration: none !important;
    }
    .card-title {
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 1rem;
        text-decoration: none !important;
    }
    .card-desc {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-bottom: 1rem;
        text-decoration: none !important;
    }
    .try-badge {
        position: absolute;
        top: 15px;
        right: 15px;
        background: rgba(255,255,255,0.2);
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: bold;
        backdrop-filter: blur(10px);
        text-decoration: none !important;
    }
    /* Remove underline from all child elements */
    .card-link * {
        text-decoration: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Configure your URLs
PROJECT1_URL = "https://medtriage.streamlit.app/"
PROJECT2_URL = "https://shopping-assistant-final.streamlit.app"

# Header
st.markdown('<div class="main-header">🤖 AI Agent Services Hub</div>', unsafe_allow_html=True)

# Create two columns for the agent cards
col1, col2 = st.columns(2)

# Project 1 - Community Solver Agent
with col1:
    st.markdown(
        f"""
        <a href="{PROJECT1_URL}" target="_blank" class="card-link">
            <div class="card-container card-1">
                <div class="try-badge">Try Now</div>
                <div class="emoji">🩺</div>
                <div class="card-title">Medical Diagnosis</div>
                <div class="card-desc">Intelligent problem-solving for community challenges and collaborative solutions</div>
            </div>
        </a>
        """,
        unsafe_allow_html=True
    )

# Project 2 - Shopping Assistant Agent
with col2:
    st.markdown(
        f"""
        <a href="{PROJECT2_URL}" target="_blank" class="card-link">
            <div class="card-container card-2">
                <div class="try-badge">Try Now</div>
                <div class="emoji">🛍️</div>
                <div class="card-title">Shopping Assistant</div>
                <div class="card-desc">Smart shopping companion for personalized recommendations and deals</div>
            </div>
        </a>
        """,
        unsafe_allow_html=True
    )

# Footer
st.markdown("""
<div style="text-align: center; color: #666; margin-top: 3rem;">
    <p>✨ Click on any service card to try it out! ✨</p>
</div>
""", unsafe_allow_html=True)