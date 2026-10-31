"""Fetch the last seven days of arXiv submissions for the configured categories.

Added for weekly collection in the andrew-zyf deployment.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import arxiv
import requests


def main():
    categories = [c.strip() for c in os.environ["CATEGORIES"].split(",") if c.strip()]
    if not categories:
        raise ValueError("CATEGORIES must contain at least one category")

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    category_query = " OR ".join(f"cat:{category}" for category in categories)
    start_term = start.strftime("%Y%m%d%H%M")
    end_term = (now + timedelta(minutes=1)).strftime("%Y%m%d%H%M")
    query = f"({category_query}) AND submittedDate:[{start_term} TO {end_term}]"
    search = arxiv.Search(query=query, max_results=None, sort_by=arxiv.SortCriterion.SubmittedDate,
                          sort_order=arxiv.SortOrder.Descending)
    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=0)
    seen = set()
    count = 0

    with open(sys.argv[1], "w", encoding="utf-8") as output:
        for attempt in range(5):
            try:
                for paper in client.results(search):
                    if paper.published < start:
                        break
                    if paper.published >= now:
                        continue
                    paper_id = paper.get_short_id().split("v")[0]
                    if paper_id in seen:
                        continue
                    seen.add(paper_id)
                    item = {
                        "id": paper_id,
                        "categories": paper.categories,
                        "pdf": paper.pdf_url,
                        "abs": paper.entry_id,
                        "authors": [author.name for author in paper.authors],
                        "title": paper.title,
                        "comment": paper.comment,
                        "summary": paper.summary,
                    }
                    output.write(json.dumps(item, ensure_ascii=False) + "\n")
                    count += 1

                break
            except (arxiv.ArxivError, requests.RequestException) as error:
                if isinstance(error, arxiv.HTTPError) and error.status != 429 and error.status < 500:
                    raise
                if attempt == 4:
                    raise
                delay = 60 * 2 ** attempt
                print(f"arXiv request failed ({type(error).__name__}); retrying in {delay}s", flush=True)
                time.sleep(delay)

    print(f"Collected {count} papers in [{start.isoformat()}, {now.isoformat()})")


if __name__ == "__main__":
    main()
