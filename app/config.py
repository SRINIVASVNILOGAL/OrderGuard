import os
from dotenv import load_dotenv
load_dotenv()

OPENROUTER_API_KEY=os.getenv("OPENROUTER_API_KEY")
TYPESAFE_API_KEY=os.getenv("TYPESAFE_API_KEY")
MONGODB_URI=os.getenv("MONGODB_URI")
LANGSMITH_API_KEY=os.getenv("LANGSMITH_API_KEY")