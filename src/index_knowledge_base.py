"""
RAG Ingestion Pipeline — Embed and index rag_context.json into Azure AI Search.

Reads documents from data/rca_poc/rag_context.json (or Azure Blob Storage in prod),
calls Azure OpenAI text-embedding-3-small to generate embeddings, and upserts
all documents into the Azure AI Search index.

Two-track retrieval design:
  - github_pr / jira_ticket / terraform_pr → no signature filter at index time
    (retrieved by time + service; LLM reads code_diff to correlate)
  - runbook → incident_signature tagged for exact-match retrieval

Index schema:
  id, content, code_diff, embedding (float[1536]), doc_type,
  incident_signature, service_affected, author, timestamp

Usage:
    python src/index_knowledge_base.py --config config/dev.yml
    python src/index_knowledge_base.py --config config/dev.yml --source blob

Environment variables:
    AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID
    AZURE_OPENAI_ENDPOINT  (e.g. https://<name>.openai.azure.com/)
    AZURE_OPENAI_API_KEY
    AZURE_SEARCH_ENDPOINT  (e.g. https://<name>.search.windows.net)
    AZURE_SEARCH_ADMIN_KEY
"""

import argparse
import json
import os
import time

import yaml
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
    SearchableField,
)
from openai import AzureOpenAI

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
INDEX_NAME = "rca-knowledge-base"
BATCH_SIZE = 16  # documents per embedding API call
RETRY_DELAY_SEC = 2


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Embed and index RCA knowledge base into Azure AI Search")
    p.add_argument("--config", required=True, help="Path to environment config YAML (e.g. config/dev.yml)")
    p.add_argument(
        "--source",
        choices=["local", "blob"],
        default="local",
        help="Where to read rag_context.json from",
    )
    p.add_argument("--rag_context_path", default="data/rca_poc/rag_context.json")
    return p.parse_args()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2024-02-01",
    )


def get_search_clients():
    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    key = os.environ["AZURE_SEARCH_ADMIN_KEY"]
    credential = AzureKeyCredential(key)
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
    search_client = SearchClient(
        endpoint=endpoint,
        index_name=INDEX_NAME,
        credential=credential,
    )
    return index_client, search_client


def ensure_index(index_client: SearchIndexClient) -> None:
    """Create the Azure AI Search index if it does not exist."""
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="code_diff", type=SearchFieldDataType.String, filterable=False),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="hnsw-profile",
        ),
        SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="incident_signature", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="service_affected", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="author", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="timestamp", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="incident_id", type=SearchFieldDataType.String, filterable=True),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
        profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw-config")],
    )

    index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)

    try:
        index_client.get_index(INDEX_NAME)
        print(f"[search] Index '{INDEX_NAME}' already exists — skipping creation.")
    except Exception:
        index_client.create_index(index)
        print(f"[search] Created index '{INDEX_NAME}'.")


def load_documents_local(path: str) -> list:
    with open(path) as f:
        return json.load(f)


def load_documents_blob(cfg: dict) -> list:
    """Download rag_context.json from Azure Blob Storage."""
    from azure.storage.blob import BlobServiceClient
    from azure.identity import ClientSecretCredential as _Cred

    credential = _Cred(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
    )
    account_url = f"https://{os.environ['STORAGE_ACCOUNT_DEV']}.blob.core.windows.net"
    blob_client = BlobServiceClient(account_url=account_url, credential=credential)

    container = cfg["storage"]["container_name"]
    blob_name = "datasets/rag_context.json"

    data = blob_client.get_blob_client(container=container, blob=blob_name).download_blob().readall()
    return json.loads(data)


def embed_batch(client: AzureOpenAI, texts: list) -> list:
    """Embed a batch of texts, retrying once on rate limit."""
    for attempt in range(2):
        try:
            response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
            return [item.embedding for item in response.data]
        except Exception as e:
            if attempt == 0:
                print(f"  [embed] Retrying after error: {e}")
                time.sleep(RETRY_DELAY_SEC)
            else:
                raise


def build_embed_text(doc: dict) -> str:
    """Concatenate content + code_diff for richer embedding (PRs)."""
    parts = [doc["content"]]
    if doc.get("code_diff"):
        parts.append(doc["code_diff"])
    return "\n\n".join(parts)


def index_documents(
    oai_client: AzureOpenAI,
    search_client: SearchClient,
    documents: list,
) -> None:
    total = len(documents)
    print(f"[index] Embedding and indexing {total} documents in batches of {BATCH_SIZE}...")

    for start in range(0, total, BATCH_SIZE):
        batch = documents[start : start + BATCH_SIZE]
        texts = [build_embed_text(doc) for doc in batch]

        print(f"  [embed] Batch {start // BATCH_SIZE + 1} ({start}–{min(start + BATCH_SIZE, total) - 1})")
        embeddings = embed_batch(oai_client, texts)

        search_docs = []
        for doc, embedding in zip(batch, embeddings):
            search_docs.append(
                {
                    "id": doc["id"],
                    "content": doc["content"],
                    "code_diff": doc.get("code_diff") or "",
                    "embedding": embedding,
                    "doc_type": doc["doc_type"],
                    "incident_signature": doc.get("incident_signature") or "unknown",
                    "service_affected": doc.get("service_affected") or "*",
                    "author": doc.get("author") or "",
                    "timestamp": doc.get("timestamp") or "",
                    "incident_id": doc.get("incident_id") or "",
                }
            )

        result = search_client.upload_documents(documents=search_docs)
        succeeded = sum(1 for r in result if r.succeeded)
        print(f"  [index] Upserted {succeeded}/{len(batch)} documents.")

    print(f"\n[index] Done. Total documents indexed: {total}")


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    print(f"[index_knowledge_base] Environment: {cfg.get('environment', '?')}")

    if args.source == "blob":
        print("[index] Loading documents from Azure Blob Storage...")
        documents = load_documents_blob(cfg)
    else:
        print(f"[index] Loading documents from: {args.rag_context_path}")
        documents = load_documents_local(args.rag_context_path)

    print(f"[index] Loaded {len(documents)} documents.")

    oai_client = get_openai_client()
    index_client, search_client = get_search_clients()

    ensure_index(index_client)
    index_documents(oai_client, search_client, documents)


if __name__ == "__main__":
    main()
