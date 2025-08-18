from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from .config import settings

def get_embeddings():
    return AzureOpenAIEmbeddings(
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        azure_deployment=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    )

def get_llm():
    return AzureChatOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        azure_deployment=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
        temperature=0,
    )
