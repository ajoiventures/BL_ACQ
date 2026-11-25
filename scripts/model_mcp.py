"""Read-only private MCP adapter. Start only in a trusted local environment."""
import os
from mcp.server.fastmcp import FastMCP
from local_model import propose_or_review

server = FastMCP("Black River Local Model", host="127.0.0.1", port=8765)

@server.tool()
def classify_mail(document: str) -> dict:
    """Return an unverified mail classification and source-backed deadline proposal."""
    if not document.strip() or len(document)>16000:
        raise ValueError("Provide 1 to 16000 characters of document text.")
    return propose_or_review(document, os.environ.get("BR_LOCAL_MODEL"))

if __name__=="__main__":
    server.run(transport="streamable-http")
