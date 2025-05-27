from fastapi import FastAPI, HTTPException, WebSocket
from utils.ollama_client import OllamaChatClient

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from utils.tool_manager import ToolManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="Multi-Tool MCP Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize tool manager
tool_manager = ToolManager()

# Pydantic models
class ToolExecutionRequest(BaseModel):
    tool_server: str  # e.g., "calculator_tool"
    function_name: str  # e.g., "add"
    parameters: Dict[str, Any]

class ToolExecutionResponse(BaseModel):
    success: bool
    result: Any = None
    error: str = None
    tool_server: str = None
    function_name: str = None

# API Routes
@app.get("/")
async def root():
    return {
        "message": "Multi-Tool MCP Server Running",
        "loaded_tools": len(tool_manager.loaded_tools),
        "available_endpoints": [
            "/tools - List all tools",
            "/tools/{tool_name} - Get specific tool info",
            "/execute - Execute a tool function",
            "/ws - WebSocket connection",
            "/debug/tools-directory - Debug tools path"
        ]
    }

#? The MODEL will be replaced with a choose option from the frontend, just do not forget about it.
MODEL = "mistral"
ollama_bot = OllamaChatClient(model=MODEL)  # ou llama3



@app.get("/tools")
async def list_all_tools():
    """Get all available tools organized by tool server"""
    return {
        "tools": tool_manager.get_all_tools(),
        "loaded_servers": list(tool_manager.loaded_tools.keys())
    }

@app.get("/tools/{tool_name}")
async def get_tool_details(tool_name: str):
    """Get detailed information about a specific tool server"""
    tool_info = tool_manager.get_tool_info(tool_name)
    if not tool_info:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    return {
        "tool_name": tool_name,
        "available_functions": tool_info["tools"],
        "server_info": {
            "name": tool_info["name"],
            "function_count": len(tool_info["tools"])
        }
    }

@app.post("/execute", response_model=ToolExecutionResponse)
async def execute_tool_function(request: ToolExecutionRequest):
    """Execute a specific function from a tool server"""
    try:
        result = await tool_manager.execute_tool(
            request.tool_server,
            request.function_name,
            request.parameters
        )
        
        return ToolExecutionResponse(
            success=True,
            result=result,
            tool_server=request.tool_server,
            function_name=request.function_name
        )
        
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return ToolExecutionResponse(
            success=False,
            error=str(e),
            tool_server=request.tool_server,
            function_name=request.function_name
        )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("✅ WebSocket connection established")

    chat_history = []

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"📩 Message received: {data}")
            message = json.loads(data)

            if message.get("type") == "execute_tool":
                logger.info(f"⚙️ Executing tool: {message.get('tool_server')} -> {message.get('function_name')}")
                try:
                    result = await tool_manager.execute_tool(
                        message["tool_server"],
                        message["function_name"],
                        message.get("parameters", {})
                    )
                    logger.info("✅ Tool execution succeeded")
                    await websocket.send_text(json.dumps({
                        "type": "execution_result",
                        "success": True,
                        "result": result,
                        "tool_server": message["tool_server"],
                        "function_name": message["function_name"]
                    }))
                except Exception as e:
                    logger.error(f"❌ Tool execution failed: {e}")
                    await websocket.send_text(json.dumps({
                        "type": "execution_result",
                        "success": False,
                        "error": str(e),
                        "tool_server": message.get("tool_server"),
                        "function_name": message.get("function_name")
                    }))

            elif message.get("type") == "list_tools":
                logger.info("📚 Listing all tools")
                tools = tool_manager.get_all_tools()
                await websocket.send_text(json.dumps({
                    "type": "tools_list",
                    "tools": tools
                }))

            elif message.get("type") == "chat":
                prompt = message.get("prompt")
                if prompt:
                    logger.info(f"🧠 Chat prompt: {prompt}")
                    chat_history.append({"role": "user", "content": prompt})
                    try:
                        response = await ollama_bot.chat(chat_history)
                        chat_history.append({"role": "assistant", "content": response})
                        logger.info(f"🗨️ Bot response: {response}")
                        await websocket.send_text(json.dumps({
                            "type": "chat_response",
                            "success": True,
                            "response": response
                        }))
                    except Exception as e:
                        logger.error(f"❌ Chatbot error: {e}")
                        await websocket.send_text(json.dumps({
                            "type": "chat_response",
                            "success": False,
                            "error": str(e)
                        }))
    except Exception as e:
        logger.error(f"💥 WebSocket connection error: {e}")

@app.get("/debug/tools-directory")
async def debug_tools_directory():
    """Debug endpoint to check tools directory resolution"""
    return tool_manager.get_tools_directory_info()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "loaded_tools": len(tool_manager.loaded_tools),
        "tool_servers": list(tool_manager.loaded_tools.keys())
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("=== Multi-Tool MCP Server Starting ===")
    logger.info(f"Tools directory: {tool_manager.tools_directory}")
    logger.info("Discovering and loading MCP tools...")
    await tool_manager.discover_and_load_tools()
    logger.info(f"✓ Loaded {len(tool_manager.loaded_tools)} tool servers")
    logger.info("=== Server Ready ===")
    
    yield  # This is where the application runs
    
    # Shutdown logic
    logger.info("Shutting down all MCP tools...")
    await tool_manager.shutdown_all()
    logger.info("=== Server Shutdown Complete ===")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8000,
        reload=True,
        log_level="info"
    )