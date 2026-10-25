"""
One01 RAG pipeline.

  ingest.py      load PDF / Markdown / text → sections → overlapping chunks
  embeddings.py  Gemini embeddings (local MiniLM fallback) as normalized vectors
  retriever.py   hybrid search: dense cosine + BM25, fused with Reciprocal Rank Fusion
  service.py     ingestion, lesson memory, query rewriting, grounded prompt context
"""
