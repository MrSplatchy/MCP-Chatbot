from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import logging
from utils.tool_manager import ToolManager
from utils.ollama_client import OllamaChatClient
import os
from pathlib import Path

# Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables globales
MODEL = "mistral"
ollama_bot = OllamaChatClient(model=MODEL)
tool_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global tool_manager
    
    # 🚀 Démarrage
    logger.info("🚀 Démarrage du serveur...")
    tool_manager = ToolManager(str(Path(__file__).parent / "tools"))
    await tool_manager.load_all_tools()
    
    if tool_manager.is_ready():
        stats = tool_manager.get_stats()
        logger.info(f"✅ {stats['tools_loaded']} outils chargés avec {stats['total_functions']} fonctions")
    else:
        logger.warning("⚠️  Aucun outil chargé")
    
    yield
    
    # 🔴 Arrêt
    logger.info("🔴 Arrêt du serveur...")
    if tool_manager:
        await tool_manager.shutdown_all()

# Application FastAPI
app = FastAPI(
    title="AI Tool Server", 
    description="Serveur d'IA avec outils MCP",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Page d'accueil avec infos du serveur"""
    if not tool_manager:
        return {"status": "starting", "message": "Serveur en cours de démarrage..."}
    
    stats = tool_manager.get_stats()
    return {
        "status": "ready" if tool_manager.is_ready() else "no_tools",
        "model": MODEL,
        **stats
    }

@app.get("/tools")
async def list_tools():
    """Liste tous les outils disponibles"""
    if not tool_manager:
        return {"error": "ToolManager non initialisé"}
    
    return {
        "tools": tool_manager.get_all_tools(),
        "stats": tool_manager.get_stats()
    }

@app.get("/tools/{tool_name}")
async def get_tool_info(tool_name: str):
    """Informations détaillées sur un outil"""
    if not tool_manager:
        return {"error": "ToolManager non initialisé"}
    
    info = tool_manager.get_tool_info(tool_name)
    if not info:
        return {"error": f"Outil '{tool_name}' non trouvé"}
    
    return {
        "tool_name": tool_name,
        "functions": info.get("functions", []),
        "available": True
    }

@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket pour chat avec l'IA"""
    await websocket.accept()
    chat_history = []
    
    # Message de bienvenue
    await websocket.send_text(json.dumps({
        "type": "info",
        "message": f"🤖 Connecté! Modèle: {MODEL}",
        "tools_available": tool_manager.is_ready() if tool_manager else False
    }))
    
    try:
        while True:
            # Recevoir le message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "chat":
                user_prompt = message.get("prompt", "")
                chat_history.append({"role": "user", "content": user_prompt})
                
                try:
                    # Chat avec outils disponibles
                    available_tools = tool_manager.get_all_tools() if tool_manager else {}
                    response = await ollama_bot.chat(chat_history, available_tools)
                    
                    chat_history.append({"role": "assistant", "content": response})
                    
                    await websocket.send_text(json.dumps({
                        "type": "chat_response",
                        "response": response,
                        "success": True
                    }))
                    
                except Exception as e:
                    logger.error(f"Erreur chat: {e}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Erreur: {str(e)}",
                        "success": False
                    }))
            
            # 
            elif message.get("type") == "reset":
                chat_history = []
                await websocket.send_text(json.dumps({
                    "type": "reset_ok",
                    "message": "💬 Conversation réinitialisée"
                }))
            
            elif message.get("type") == "tools_status":
                stats = tool_manager.get_stats() if tool_manager else {}
                await websocket.send_text(json.dumps({
                    "type": "tools_status",
                    **stats
                }))
                
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="localhost", 
        port=8002, 
        reload=True,
        log_level="info",
        root_path=""
    )