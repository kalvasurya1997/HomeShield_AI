from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
import os

def embeddings():
    return AzureOpenAIEmbeddings(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
    )

def chat_client(temperature=0):
    return AzureChatOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
        temperature=temperature,
    )

def vectorstore(namespace: str = "policies"):
    _ = Pinecone(api_key=os.environ["PINECONE_API_KEY"])  # init
    return PineconeVectorStore(
        index_name=os.environ["PINECONE_INDEX"],
        embedding=embeddings(),
        namespace=namespace,
    )
