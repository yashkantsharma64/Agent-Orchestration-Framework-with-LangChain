from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables from .env file

load_dotenv("/Users/abhinavchaudhary/Documents/Personal/Programming/Shopping Assistant UI/abh.env")

def create_llm(model_name="gemini-2.5-flash-lite", temperature=0.3):
  """
  Creates and configures a Google Gemini LLM instance.
  """
  # Check if the API key is available
  if "GOOGLE_API_KEY" not in os.environ:
      raise ValueError("Google API Key not found. Please set it in your .env file.")
  
  # Configure and return the Gemini model
  llm = ChatGoogleGenerativeAI(
      model=model_name,
      temperature=temperature,
      convert_system_message_to_human=True 
  )
  return llm

# Create the new LLM instance
llm = create_llm()
