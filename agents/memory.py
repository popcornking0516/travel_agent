# agents/memory.py
"""向量记忆模块 - Chroma + 阿里云 Embedding"""
import os
import uuid
import chromadb
from chromadb.config import Settings
from openai import OpenAI

# 初始化 Chroma（数据持久化到 chroma_db/ 目录）
chroma_client = chromadb.PersistentClient(
    path="chroma_db",
    settings=Settings(anonymized_telemetry=False)
)

# 集合：存放所有用户的对话记忆
collection = chroma_client.get_or_create_collection(name="conversation_memory")

# 阿里云 Embedding 客户端
client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL")
)

def _get_embedding(text: str) -> list:
    """将文本转为向量"""
    response = client.embeddings.create(
        model="text-embedding-v1",  
        input=text
    )
    return response.data[0].embedding


def add_message(username: str, role: str, content: str):
    """添加一条消息到记忆库"""
    if not content.strip():
        return
    embedding = _get_embedding(content)
    collection.add(
        ids=[str(uuid.uuid4())],
        embeddings=[embedding],
        metadatas=[{"username": username, "role": role}],
        documents=[content]
    )


def search_memory(username: str, query: str, n_results: int = 5) -> str:
    """搜索与查询最相关的历史消息"""
    query_embedding = _get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        where={"username": username},
        n_results=n_results
    )
    docs = results.get("documents", [[]])[0]
    if not docs:
        return ""
    return "\n".join([f"- {doc}" for doc in docs])


def delete_user_memory(username: str):
    """删除某用户的所有记忆"""
    results = collection.get(where={"username": username})
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)