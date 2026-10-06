# """Entry point for the E-Commerce MCP Server."""

# import os
# from ecommerce_mcp_server import mcp

# if __name__ == "__main__":
#     host = os.getenv("MCP_HOST", "127.0.0.1")
#     port = int(os.getenv("MCP_PORT", "8000"))
#     mcp.run(transport="http", host=host, port=port)



"""Entry point for the E-Commerce MCP Server."""

import os
from ecommerce_mcp_server import mcp

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "http":
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8000"))
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run(transport="stdio")

