"""
Quick DuckDuckGo image search connectivity test.
Run from WSL terminal: venv/bin/python app/search/test_ddg.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.search.image_search import search_images

print("=" * 60)
print("DuckDuckGo Image Search Connectivity Test")
print("=" * 60)

queries = ["cat", "mountain landscape", "Apple product design"]
for q in queries:
    results = search_images(q, max_results=2)
    if results:
        print(f"\n[OK] '{q}' → {len(results)} results")
        for r in results[:1]:
            print(f"     Title: {r['title'][:80]}")
            print(f"     Image: {r['image'][:80]}")
    else:
        print(f"\n[FAIL] '{q}' → 0 results (DuckDuckGo may be blocked or unreachable)")

print("\n" + "=" * 60)
print("Test complete. If all queries return 0, DuckDuckGo is unreachable.")
print("Possible causes: rate limiting, IP block, or no internet in WSL.")
print("=" * 60)
