import os
import importlib
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

class ToolManager:
    """Gestionnaire d'outils MCP simplifié"""
    
    def __init__(self, tools_directory: str = "tools"):
        self.tools_directory = Path(tools_directory)
        self.loaded_tools: Dict[str, Any] = {}
        
        logger.info(f"ToolManager initialisé avec le dossier: {self.tools_directory}")
    
    async def load_all_tools(self):
        """Charge tous les outils du dossier tools/"""
        
        # Créer le dossier s'il n'existe pas
        if not self.tools_directory.exists():
            logger.warning(f"Dossier {self.tools_directory} introuvable, création...")
            self.tools_directory.mkdir(parents=True, exist_ok=True)
            (self.tools_directory / "__init__.py").touch()
            logger.info("Ajoutez vos fichiers d'outils dans le dossier 'tools/'")
            return
        
        # Trouver tous les fichiers Python (sauf __init__.py)
        tool_files = [
            f for f in self.tools_directory.glob("*.py") 
            if f.name != "__init__.py"
        ]
        
        if not tool_files:
            logger.warning("Aucun fichier d'outil trouvé")
            return
        
        logger.info(f"Chargement de {len(tool_files)} outils...")
        
        # Charger chaque outil
        for tool_file in tool_files:
            await self._load_single_tool(tool_file)
    
    async def _load_single_tool(self, tool_file: Path):
        """Charge un seul outil"""
        tool_name = tool_file.stem
        
        try:
            # Importer le module
            spec = importlib.util.spec_from_file_location(tool_name, tool_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Vérifier qu'il y a un serveur MCP
            if not hasattr(module, 'mcp_server'):
                logger.warning(f"❌ {tool_name}: pas de 'mcp_server' trouvé")
                return
            
            server = module.mcp_server
            
            # Démarrer le serveur
            await server.start()
            
            # Sauvegarder l'outil
            self.loaded_tools[tool_name] = {
                "server": server,
                "functions": server.list_tools(),
                "module": module
            }
            
            logger.info(f"✅ {tool_name}: {len(server.list_tools())} fonctions chargées")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement de {tool_name}: {e}")
    
    def get_all_tools(self) -> Dict[str, List[str]]:
        """Retourne tous les outils disponibles"""
        result = {}
        for tool_name, tool_info in self.loaded_tools.items():
            result[tool_name] = tool_info["functions"]
        return result
    
    async def execute_tool(self, tool_name: str, function_name: str, parameters: Dict[str, Any]):
        """Exécute une fonction d'un outil"""
        if tool_name not in self.loaded_tools:
            raise ValueError(f"Outil '{tool_name}' non trouvé")
        
        server = self.loaded_tools[tool_name]["server"]
        return await server.call_tool(function_name, parameters)
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """Informations sur un outil spécifique"""
        return self.loaded_tools.get(tool_name, {})
    
    async def shutdown_all(self):
        """Arrête tous les serveurs d'outils"""
        for tool_name, tool_info in self.loaded_tools.items():
            try:
                await tool_info["server"].stop()
                logger.info(f"🔴 {tool_name} arrêté")
            except Exception as e:
                logger.error(f"Erreur arrêt {tool_name}: {e}")
        
        self.loaded_tools.clear()
    
    def is_ready(self) -> bool:
        """Vérifie si des outils sont chargés"""
        return len(self.loaded_tools) > 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Statistiques du gestionnaire d'outils"""
        total_functions = sum(
            len(tool["functions"]) 
            for tool in self.loaded_tools.values()
        )
        
        return {
            "tools_loaded": len(self.loaded_tools),
            "total_functions": total_functions,
            "tools_directory": str(self.tools_directory),
            "tool_names": list(self.loaded_tools.keys())
        }