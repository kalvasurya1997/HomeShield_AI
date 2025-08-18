from pathlib import Path
from pydantic import BaseModel
import os

from dotenv import load_dotenv
load_dotenv()
BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseModel):
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    AZURE_OPENAI_CHAT_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")

    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX: str = os.getenv("PINECONE_INDEX")
    PINECONE_REGION: str = os.getenv("PINECONE_REGION", "us-east-1")
    NAMESPACE: str = os.getenv("PINECONE_NAMESPACE", "policies")

    POLICY_DIR: Path = Path(os.getenv("POLICY_DIR", str(BASE_DIR / "policies_docs")))
    CUSTOMERS_CSV: Path = Path(os.getenv("CUSTOMERS_CSV", str(BASE_DIR / "homeshield_sample_data" / "customers.csv")))

settings = Settings()
