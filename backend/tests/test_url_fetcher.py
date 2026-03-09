"""Unit tests for url_fetcher.strip_html (P2.4).

Verifies that HTML structure is preserved as markdown:
  - h1–h4 → # / ## / ### / #### prefixes
  - <li>   → - bullet points
  - <pre> and <code> → fenced ``` code blocks
  - <script>/<style> removed entirely
  - Remaining tags stripped to plain text
  - Excess whitespace / blank lines normalised
"""


from app.services.url_fetcher import strip_html

# ── Headings ─────────────────────────────────────────────────────────────────


def test_h1_becomes_markdown_h1():
    result = strip_html("<h1>Getting Started</h1>")
    assert "# Getting Started" in result


def test_h2_becomes_markdown_h2():
    result = strip_html("<h2>Authentication</h2>")
    assert "## Authentication" in result


def test_h3_becomes_markdown_h3():
    result = strip_html("<h3>Request Parameters</h3>")
    assert "### Request Parameters" in result


def test_h4_becomes_markdown_h4():
    result = strip_html("<h4>Body Fields</h4>")
    assert "#### Body Fields" in result


def test_heading_with_attributes():
    """Attributes on the heading tag should not break the conversion."""
    result = strip_html('<h2 class="section-title" id="auth">Authentication</h2>')
    assert "## Authentication" in result


def test_heading_with_inner_span():
    """Inner tags inside headings are stripped, text preserved."""
    result = strip_html("<h2><span>Endpoint</span> Reference</h2>")
    assert "## Endpoint Reference" in result


def test_heading_hierarchy_preserved():
    """Multiple headings at different levels all converted correctly."""
    html = "<h1>API Docs</h1><h2>Endpoints</h2><h3>POST /create</h3>"
    result = strip_html(html)
    assert "# API Docs" in result
    assert "## Endpoints" in result
    assert "### POST /create" in result


def test_h1_before_h2_in_output():
    """h1 content appears before h2 content in the output."""
    html = "<h1>Top Level</h1><h2>Sub Level</h2>"
    result = strip_html(html)
    assert result.index("# Top Level") < result.index("## Sub Level")


# ── Lists ─────────────────────────────────────────────────────────────────────


def test_li_becomes_bullet():
    result = strip_html("<ul><li>First item</li></ul>")
    assert "- First item" in result


def test_multiple_li_each_bulleted():
    html = "<ul><li>Alpha</li><li>Beta</li><li>Gamma</li></ul>"
    result = strip_html(html)
    assert "- Alpha" in result
    assert "- Beta" in result
    assert "- Gamma" in result


def test_ordered_list_li_also_converted():
    """<ol><li> gets the same bullet treatment — ol tag itself is stripped."""
    html = "<ol><li>Step one</li><li>Step two</li></ol>"
    result = strip_html(html)
    assert "- Step one" in result
    assert "- Step two" in result


def test_li_with_inner_tags():
    """Inner tags inside <li> are stripped, text preserved."""
    result = strip_html("<li><strong>Important</strong> note</li>")
    assert "- Important note" in result


# ── Code blocks ───────────────────────────────────────────────────────────────


def test_pre_block_becomes_fenced_code():
    result = strip_html("<pre>curl -X POST /api/create</pre>")
    assert "```" in result
    assert "curl -X POST /api/create" in result


def test_pre_block_fences_surround_content():
    """Content must appear between opening and closing fences."""
    result = strip_html("<pre>SELECT * FROM users;</pre>")
    lines = result.splitlines()
    fence_indices = [i for i, ln in enumerate(lines) if ln.strip() == "```"]
    assert len(fence_indices) >= 2
    open_fence, close_fence = fence_indices[0], fence_indices[-1]
    content_lines = lines[open_fence + 1 : close_fence]
    assert any("SELECT" in ln for ln in content_lines)


def test_code_inline_becomes_fenced_code():
    result = strip_html("<code>print('hello')</code>")
    assert "```" in result
    assert "print('hello')" in result


def test_pre_with_inner_code_tag():
    """<pre><code> pattern common in API docs."""
    result = strip_html("<pre><code>GET /api/users HTTP/1.1</code></pre>")
    assert "```" in result
    assert "GET /api/users HTTP/1.1" in result


def test_pre_multiline_content_preserved():
    html = "<pre>line one\nline two\nline three</pre>"
    result = strip_html(html)
    assert "line one" in result
    assert "line two" in result
    assert "line three" in result


# ── Noise removal ─────────────────────────────────────────────────────────────


def test_script_removed():
    result = strip_html("<script>alert('xss')</script>Visible text")
    assert "alert" not in result
    assert "Visible text" in result


def test_style_removed():
    result = strip_html("<style>.btn { color: red; }</style>Content")
    assert "color" not in result
    assert "Content" in result


def test_script_with_attributes_removed():
    result = strip_html('<script src="app.js" type="text/javascript"></script>Text')
    assert "app.js" not in result
    assert "Text" in result


# ── Generic tag stripping ─────────────────────────────────────────────────────


def test_generic_tags_stripped():
    result = strip_html("<p>Hello <strong>world</strong></p>")
    assert "<p>" not in result
    assert "<strong>" not in result
    assert "Hello" in result
    assert "world" in result


def test_div_stripped():
    result = strip_html("<div class='wrapper'><p>Content</p></div>")
    assert "<div" not in result
    assert "Content" in result


# ── Whitespace normalisation ───────────────────────────────────────────────────


def test_excess_blank_lines_collapsed():
    """Three or more consecutive newlines are collapsed to two."""
    html = "<p>Para one</p>\n\n\n\n<p>Para two</p>"
    result = strip_html(html)
    assert "\n\n\n" not in result


def test_leading_trailing_whitespace_stripped():
    result = strip_html("  <p>content</p>  ")
    assert result == result.strip()


def test_result_not_empty_for_plain_html():
    result = strip_html("<html><body><p>Hello</p></body></html>")
    assert "Hello" in result


# ── Integration: API docs page structure ─────────────────────────────────────


def test_api_docs_structure_preserved():
    """Simulate a minimal API docs page and check key structural elements."""
    html = """
    <html>
    <head><style>body { font-family: sans-serif; }</style></head>
    <body>
      <h1>My API</h1>
      <h2>Authentication</h2>
      <p>Use Bearer tokens.</p>
      <h3>POST /token</h3>
      <ul>
        <li>grant_type: required</li>
        <li>client_id: required</li>
      </ul>
      <h4>Example</h4>
      <pre><code>curl -X POST https://api.example.com/token \
  -d grant_type=client_credentials</code></pre>
      <script>console.log('tracker');</script>
    </body>
    </html>
    """
    result = strip_html(html)

    # Headings preserved
    assert "# My API" in result
    assert "## Authentication" in result
    assert "### POST /token" in result
    assert "#### Example" in result

    # Bullets preserved
    assert "- grant_type: required" in result
    assert "- client_id: required" in result

    # Code preserved
    assert "```" in result
    assert "curl -X POST" in result

    # Noise removed
    assert "console.log" not in result
    assert "font-family" not in result
    assert "<html>" not in result
