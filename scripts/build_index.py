#!/usr/bin/env python3
"""
Build embeddings and vector index for paper-compass.

Usage:
    # Index all PDF text chunks
    python scripts/build_index.py --library data/zotero-export/library.json
        [--db-path ./data/vectordb]
        [--text-dir ./data/texts]
        [--extract-text]          # extract text if not already cached

    # Index wiki pages
    python scripts/build_index.py --wiki --wiki-root ./wiki
        [--db-path ./data/vectordb]
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from miniresearch.embedder import Embedder
from miniresearch.vector_store import VectorStore
from miniresearch.config import get_provider_config, load_all_configs


def _load_env():
    """Load .env into os.environ if not already set."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if val and not os.environ.get(key.strip()):
                    os.environ[key.strip()] = val.strip()


def _init_embedder() -> Embedder:
    """Initialize embedder from project config + env."""
    _load_env()
    configs = load_all_configs("configs")

    embedder = Embedder()

    try:
        provider = get_provider_config("embedding_main", configs)
        embedder.configure_cloud(
            provider="volcengine",
            base_url=provider.get("base_url", ""),
            api_key=provider.get("api_key", ""),
            model=provider.get("model", ""),
            dimension=2048,  # doubao-embedding-vision-250615
        )
        print(f"  Embedding: cloud (volcengine, dim={embedder.dimension})")
    except Exception as e:
        print(f"  Cloud embedding unavailable ({e}), falling back to local bge-base")
        embedder.configure_local("bge-base")
        print(f"  Embedding: local (bge-base, dim={embedder.dimension})")

    return embedder


def index_papers(args):
    """Index PDF text chunks into ChromaDB."""
    library_path = Path(args.library)
    if not library_path.exists():
        print(f"ERROR: library.json not found: {library_path}")
        print("Run sync_zotero.py --extract-text first.")
        sys.exit(1)

    with open(library_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    embedder = _init_embedder()
    store = VectorStore(
        db_path=args.db_path,
        collection_name="papers",
        embedding_model_id=embedder.model_id,
    )

    chunks_added = 0
    batch_texts = []
    batch_ids = []
    batch_metas = []

    for item in items:
        pdf_path = item.get("pdf_path", "")
        key = item.get("key", "")

        if not pdf_path or not Path(pdf_path).exists():
            continue

        # Load text from cache (or extract on-the-fly)
        text_file = item.get("text_file", "")
        full_text = ""
        if text_file and Path(text_file).exists():
            full_text = Path(text_file).read_text(encoding="utf-8")
        elif args.extract_text:
            try:
                from miniresearch.pdf_extract import PDFExtractor
                full_text = PDFExtractor(pdf_path).extract_all_text()
            except Exception:
                continue
        else:
            continue

        if not full_text.strip():
            continue

        # In-memory sliding window chunking (avoid re-opening PDF)
        cs, ol, ci = 1500, 200, 0
        for pos in range(0, len(full_text), cs - ol):
            chunk_text = full_text[pos:pos + cs].strip()
            if len(chunk_text) < 50:
                continue
            batch_texts.append(chunk_text[:2000])
            batch_ids.append(f"{key}_c{ci}")
            batch_metas.append({
                "item_key": key,
                "title": item.get("title", ""),
                "year": item.get("year"),
                "authors": ", ".join(item.get("authors", [])),
                "collections": ", ".join(item.get("collections", [])),
                "tags": ", ".join(item.get("tags", [])),
            })
            ci += 1

            # Embed and store in batches
            if len(batch_texts) >= 32:
                embeddings = embedder.embed(batch_texts)
                store.add_chunks(batch_ids, batch_texts, batch_metas, embeddings)
                chunks_added += len(batch_texts)
                print(f"  Indexed {chunks_added} chunks...")
                batch_texts = []
                batch_ids = []
                batch_metas = []

    # Final batch
    if batch_texts:
        embeddings = embedder.embed(batch_texts)
        store.add_chunks(batch_ids, batch_texts, batch_metas, embeddings)
        chunks_added += len(batch_texts)

    # Build BM25
    store.build_bm25()
    print(f"\n  Total chunks indexed: {chunks_added}")
    print(f"  Collection: {store.collection_name} ({store.count()} vectors)")


def index_wiki(args):
    """Index wiki markdown pages into ChromaDB."""
    wiki_root = Path(args.wiki_root)
    if not wiki_root.exists():
        print(f"ERROR: Wiki root not found: {wiki_root}")
        sys.exit(1)

    embedder = _init_embedder()
    store = VectorStore(
        db_path=args.db_path,
        collection_name="wiki",
        embedding_model_id=embedder.model_id,
    )

    pages_indexed = 0
    for md_file in sorted(wiki_root.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        if not content.strip():
            continue

        # Chunk by heading sections (rough)
        sections = content.split("\n## ")
        for i, section in enumerate(sections):
            text = section[:2000]
            if not text.strip():
                continue

            chunk_id = f"{md_file.stem}_s{i}"
            embedding = embedder.embed_single(text)

            store.add_chunks(
                [chunk_id],
                [text],
                [{"page_path": str(md_file), "title": md_file.stem, "section": i}],
                [embedding],
            )
            pages_indexed += 1

    store.build_bm25()
    print(f"\n  Wiki sections indexed: {pages_indexed}")
    print(f"  Collection: {store.collection_name} ({store.count()} vectors)")


def main():
    parser = argparse.ArgumentParser(description="Build vector index for paper-compass")
    parser.add_argument("--library", default="data/zotero-export/library.json")
    parser.add_argument("--db-path", default="./data/vectordb")
    parser.add_argument("--text-dir", default="./data/texts")
    parser.add_argument("--extract-text", action="store_true")
    parser.add_argument("--wiki", action="store_true", help="Index wiki pages instead of papers")
    parser.add_argument("--wiki-root", default="./wiki")
    args = parser.parse_args()

    if args.wiki:
        index_wiki(args)
    else:
        index_papers(args)


if __name__ == "__main__":
    main()
