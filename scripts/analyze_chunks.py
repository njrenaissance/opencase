#!/usr/bin/env python3
"""Analyze chunk distribution in Qdrant to determine optimal chunk size."""

from collections import defaultdict
from qdrant_client import QdrantClient
import statistics

QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION = "gideon"

def analyze_chunks():
    client = QdrantClient(url=QDRANT_URL, timeout=60)

    print("Scrolling through entire Qdrant collection...", flush=True)

    # Get collection info first
    collection_info = client.get_collection(COLLECTION)
    total_points = collection_info.points_count
    print(f"Total points in collection: {total_points}\n")

    # Scroll through all points
    all_points = []
    offset = None
    batch_num = 1
    while True:
        points, next_offset = client.scroll(
            collection_name=COLLECTION,
            limit=5000,
            offset=offset,
            with_payload=True,
        )
        if not points:
            break
        all_points.extend(points)
        print(f"  Batch {batch_num}: Retrieved {len(points)} chunks (total: {len(all_points)})", flush=True)
        offset = next_offset
        batch_num += 1
        if offset is None:
            break

    print(f"Total retrieved: {len(all_points)} chunks\n")
    points = all_points

    # Analyze by document
    doc_info: dict[str, dict] = defaultdict(lambda: {"chunks": 0, "total_chars": 0, "sizes": []})

    for point in points:
        payload = point.payload or {}
        doc_id = str(payload.get("document_id", ""))
        chunk_idx = payload.get("chunk_index", 0)
        text = str(payload.get("text", ""))
        text_len = len(text)

        if doc_id:
            doc_info[doc_id]["chunks"] += 1
            doc_info[doc_id]["total_chars"] += text_len
            doc_info[doc_id]["sizes"].append(text_len)

    # Statistics
    all_chunk_sizes = []
    all_doc_sizes = []

    for doc_id, info in doc_info.items():
        all_chunk_sizes.extend(info["sizes"])
        all_doc_sizes.append(info["total_chars"])

    print(f"\n{'='*60}")
    print(f"QDRANT CHUNK ANALYSIS")
    print(f"{'='*60}")
    print(f"Total documents: {len(doc_info)}")
    print(f"Total chunks: {len(all_chunk_sizes)}")
    print(f"Total characters indexed: {sum(all_doc_sizes):,}")

    print(f"\n{'CHUNK SIZE STATISTICS':^60}")
    print(f"{'-'*60}")
    print(f"Min chunk size: {min(all_chunk_sizes):,} chars")
    print(f"Max chunk size: {max(all_chunk_sizes):,} chars")
    print(f"Mean chunk size: {statistics.mean(all_chunk_sizes):,.0f} chars")
    print(f"Median chunk size: {statistics.median(all_chunk_sizes):,.0f} chars")
    print(f"Std dev: {statistics.stdev(all_chunk_sizes):,.0f} chars")

    print(f"\n{'DOCUMENT SIZE STATISTICS':^60}")
    print(f"{'-'*60}")
    print(f"Min document size: {min(all_doc_sizes):,} chars")
    print(f"Max document size: {max(all_doc_sizes):,} chars")
    print(f"Mean document size: {statistics.mean(all_doc_sizes):,.0f} chars")
    print(f"Median document size: {statistics.median(all_doc_sizes):,.0f} chars")

    # Percentiles for chunk size
    sorted_chunks = sorted(all_chunk_sizes)
    chunk_p50 = sorted_chunks[int(len(sorted_chunks) * 0.50)]
    chunk_p75 = sorted_chunks[int(len(sorted_chunks) * 0.75)]
    chunk_p90 = sorted_chunks[int(len(sorted_chunks) * 0.90)]
    chunk_p95 = sorted_chunks[int(len(sorted_chunks) * 0.95)]

    print(f"\n{'CHUNK SIZE PERCENTILES':^60}")
    print(f"{'-'*60}")
    print(f"50th percentile (median): {chunk_p50:,} chars")
    print(f"75th percentile: {chunk_p75:,} chars")
    print(f"90th percentile: {chunk_p90:,} chars")
    print(f"95th percentile: {chunk_p95:,} chars")

    # Percentiles for document size
    sorted_docs = sorted(all_doc_sizes)
    doc_p50 = sorted_docs[int(len(sorted_docs) * 0.50)]
    doc_p75 = sorted_docs[int(len(sorted_docs) * 0.75)]
    doc_p90 = sorted_docs[int(len(sorted_docs) * 0.90)]
    doc_p95 = sorted_docs[int(len(sorted_docs) * 0.95)]

    print(f"\n{'DOCUMENT SIZE PERCENTILES':^60}")
    print(f"{'-'*60}")
    print(f"50th percentile (median): {doc_p50:,} chars")
    print(f"75th percentile: {doc_p75:,} chars")
    print(f"90th percentile: {doc_p90:,} chars")
    print(f"95th percentile: {doc_p95:,} chars")

    # Chunks per document distribution
    chunks_per_doc = [info["chunks"] for info in doc_info.values()]
    print(f"\n{'CHUNKS PER DOCUMENT':^60}")
    print(f"{'-'*60}")
    print(f"Min chunks per doc: {min(chunks_per_doc)}")
    print(f"Max chunks per doc: {max(chunks_per_doc)}")
    print(f"Mean chunks per doc: {statistics.mean(chunks_per_doc):.1f}")
    print(f"Median chunks per doc: {statistics.median(chunks_per_doc):.0f}")

    # Recommendation
    print(f"\n{'RECOMMENDATION':^60}")
    print(f"{'-'*60}")
    avg_doc_size = statistics.mean(all_doc_sizes)
    current_chunk_size = 3000

    if statistics.median(chunks_per_doc) > 3:
        recommended = int(avg_doc_size / 2)
        print(f"Current chunk size (3000) splits most docs into {statistics.median(chunks_per_doc):.0f}+ pieces.")
        print(f"Average document is {avg_doc_size:,.0f} chars.")
        print(f"\nRECOMMENDED: {recommended:,} chars")
        print(f"This would result in ~2 chunks per document on average.")
    else:
        print(f"Current chunk size is appropriate.")

if __name__ == "__main__":
    analyze_chunks()
