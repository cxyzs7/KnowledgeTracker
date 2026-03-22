# tests/test_sources/test_github_trending.py
import respx, httpx
from knowledge_tracker.sources.github_trending import fetch

TRENDING_HTML = """
<html><body>
<article class="Box-row">
  <h2><a href="/owner/repo">owner / repo</a></h2>
  <p>A cool project</p>
  <span class="d-inline-block float-sm-right">123 stars today</span>
</article>
</body></html>"""

@respx.mock
def test_fetch_returns_repos():
    respx.get("https://github.com/trending").mock(
        return_value=httpx.Response(200, text=TRENDING_HTML)
    )
    articles = fetch(language="")
    assert len(articles) == 1
    assert "repo" in articles[0].title.lower()
    assert articles[0].source == "github_trending"
