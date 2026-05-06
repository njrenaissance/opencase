# ADR 0001: Recursive Character Chunking Strategy

**Status:** Accepted  
**Date:** 2026-05-05  
**Deciders:** Jonathan Phillips

## Context

Gideon ingests criminal appellate briefs (5KB–240KB documents) and must split them into chunks for semantic embedding and RAG retrieval. Chunk size directly impacts:

- **Embedding quality**: Larger chunks preserve semantic context but may exceed token limits
- **Retrieval precision**: Smaller chunks are more granular but may fragment important concepts
- **Performance**: Larger batches reduce API overhead; smaller batches fit memory constraints
- **Cost**: Fewer embeddings = lower compute (Ollama local, so cost is latency)

## Decision

Use **recursive character splitting** with:
- **Chunk size**: 8,000 characters (≈2,000 tokens with nomic-embed-text)
- **Overlap**: 2,000 characters (25% of chunk size)
- **Min merge size**: 500 characters (merge tiny chunks with neighbors)
- **Separators** (priority order): `["\n\n", "\n", ". ", " ", ""]`

## Rationale

### Why Recursive Character Splitting?

1. **Semantic preservation**: Splits at paragraph (double newline) → sentence → word boundaries, preserving context better than fixed-size byte splitting
2. **Whitespace resilience**: Works with OCR artifacts and inconsistent formatting common in scanned legal documents
3. **No model dependency**: Doesn't require tokenizer (avoiding token-count variance across models/versions)
4. **Deterministic**: Same input always produces same chunks (important for reproducibility)

### Why 8,000 characters?

**Previous attempts:**
- **3,000 chars**: Created 7+ chunks per average document (53KB), too fragmented for legal reasoning
- **12,000 chars**: Caused Ollama /api/embed 400 errors (token limit exceeded at batch size 100)

**Validation via corpus analysis (74 documents, 667 chunks):**
```
Mean chunk:       5,837 chars
Median:           6,620 chars
95th percentile:  7,891 chars  ← safe margin under 8,000 limit
Chunks per doc:   9.0 avg      ← good granularity for appellate briefs
```

**Token utilization:**
- 8,000 chars ÷ 0.25 tokens/char ≈ 2,000 tokens per chunk
- Batch size 20 (reduced from 100) ≈ 40KB per request
- Ollama /api/embed handles this reliably

### Why 2,000 character overlap (25%)?

- **Captures context bridges**: Important for appellate briefs where relevant law spans paragraph boundaries
- **Prevents semantic cliffs**: Avoids losing critical information at chunk boundaries
- **Standard practice**: 20–25% overlap is recommended in RAG literature

### Why 500 character min merge?

- **Prevents fragmentation**: Chunks smaller than 500 chars (headers, citations, formatting) are merged with adjacent chunks
- **Reduces noise**: Avoids embedding isolated page numbers, case citations, or footnotes
- **Keeps document flow**: Maintains readability of merged context

### Why these separators?

Priority order preserves semantics:
1. `\n\n` — paragraph break (strongest semantic boundary)
2. `\n` — line break (section/item boundary)
3. `. ` — sentence boundary (standard punctuation)
4. ` ` — word break (last resort, maintains words together)
5. `` (empty) — character-level splitting (avoid unless necessary)

This mirrors langchain's `RecursiveCharacterTextSplitter` defaults, which are proven across millions of RAG deployments.

## Alternatives Considered

### 1. Fixed Token-Based Splitting
- **Rejected**: Requires tokenizer per model; token counts vary by model version
- Example: GPT-4 tokenizer != Claude tokenizer ≠ nomic-embed-text tokenizer

### 2. Semantic/Sentence Splitting (NLTK/spaCy)
- **Rejected**: Requires NLP model (slower, dependency bloat); fails on malformed legal text and OCR artifacts
- Works for clean prose, fails on appellate briefs with inconsistent formatting

### 3. Document-Aware Splitting (Markdown headers)
- **Rejected**: Assumes structured documents; appellate briefs are flat PDFs with minimal markup
- Useful for docs, not for court filings

### 4. Larger Chunks (12,000+ chars)
- **Rejected**: Causes Ollama embedding API failures (batch size × chunk size exceeds API limits)
- See 12,000 attempt above

## Consequences

### Positive
✅ Reliable embedding (no 400 errors on Ollama)  
✅ Good semantic granularity (9 chunks per 53KB document)  
✅ Preserves paragraph/sentence structure of briefs  
✅ Overlap provides context continuity  
✅ Consistent across corpus (95% within safe margin)  
✅ Works with OCR text (whitespace-agnostic)  

### Negative
- ⚠️ Smaller chunks → more embeddings → longer ingestion time
- ⚠️ Overlap creates duplicate vectors in Qdrant (slight storage overhead, mitigated by deduplication at query time)

## Monitoring & Future Adjustments

**Track these metrics:**
- Chunk size distribution (percentiles) — alert if 95th percentile approaches 8,000
- Chunks per document — should remain 7–12 for appellate briefs
- Query relevance — measure via NDCG@5 on known-good queries
- Ollama embedding latency — per-chunk and per-batch

**Triggers to reconsider:**
- Consistent embedding failures (> 1% of documents)
- Query precision drops below baseline
- New corpus types (e.g., trial transcripts, motions) show poor chunk fit

## Related Decisions

- **Caption Parsing** (ADR pending): Extract metadata (case number, parties, court) from document headers for metadata-based filtering
- **Hybrid Search** (future): Combine metadata filter + semantic search for domain-specific queries
- **Batch Size Tuning** (related): Reduced from 100 to 20 to stay under API request limits

## References

- [LangChain RecursiveCharacterTextSplitter](https://api.python.langchain.com/en/latest/text_splitter/langchain_text_splitters.recursive.RecursiveCharacterTextSplitter.html)
- [Nomic Embed Text Model Card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)
- RAG corpus analysis: `scripts/analyze_chunks.py`
- Current config: `backend/app/core/config.py` (ChunkingSettings)
