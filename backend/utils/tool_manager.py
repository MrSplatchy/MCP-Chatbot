import os
import sys
import importlib.util
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import asyncio
import inspect
import traceback

logger = logging.getLogger(__name__)

class ToolManager:
    """Gestionnaire d'outils MCP simplifié avec debugging amélioré"""
    
    def __init__(self, tools_directory: str = "tools"):
        self.tools_directory = (Path(__file__).parent.parent / tools_directory).resolve()
        self.loaded_tools: Dict[str, Any] = {}
        
        logger.info(f"ToolManager initialisé avec le dossier: {self.tools_directory.absolute()}")
    
    async def load_all_tools(self):

        # Vérifie si le dossier existe (pas de création automatique)
        if not self.tools_directory.exists() or not self.tools_directory.is_dir():
            logger.error(f"Dossier {self.tools_directory.absolute()} introuvable.")
            return

        # Afficher le contenu du dossier pour debug
        logger.info(f"Contenu du dossier {self.tools_directory.absolute()}:")
        try:
            for item in self.tools_directory.iterdir():
                logger.info(f"  - {item.name} ({'dossier' if item.is_dir() else 'fichier'})")
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du dossier: {e}")
            return

        # Ajouter au path si nécessaire
        tools_path = str(self.tools_directory.resolve())
        if tools_path not in sys.path:
            sys.path.insert(0, tools_path)
            logger.info(f"Ajouté au Python path: {tools_path}")

        # Recherche uniquement des fichiers .py dans le dossier, pas en sous-dossiers
        try:
            tool_files = [
                f for f in self.tools_directory.iterdir()
                if f.is_file() and f.suffix == ".py" and f.name != "__init__.py" and not f.name.startswith('.')
            ]
        except Exception as e:
            logger.error(f"Erreur lors de la recherche des fichiers: {e}")
            return

        if not tool_files:
            logger.warning("Aucun fichier d'outil trouvé dans le dossier")
            return

        logger.info(f"Fichiers d'outils trouvés: {[f.name for f in tool_files]}")
        logger.info(f"Chargement de {len(tool_files)} outils...")

        # Charger chaque outil
        for tool_file in tool_files:
            await self._load_single_tool(tool_file)
    
    async def _load_single_tool(self, tool_file: Path):
        """Charge un seul outil avec debugging détaillé"""
        tool_name = tool_file.stem
        
        logger.info(f"🔄 Tentative de chargement: {tool_name} ({tool_file})")
        
        try:
            # Vérifier que le fichier existe et est lisible
            if not tool_file.exists():
                logger.error(f"❌ {tool_name}: Fichier inexistant")
                return
            
            if not tool_file.is_file():
                logger.error(f"❌ {tool_name}: N'est pas un fichier")
                return
            
            # Lire le contenu pour debug
            try:
                content = tool_file.read_text(encoding='utf-8')
                logger.info(f"📄 {tool_name}: {len(content)} caractères lus")
                if len(content.strip()) == 0:
                    logger.warning(f"⚠️  {tool_name}: Fichier vide")
                    return
            except Exception as e:
                logger.error(f"❌ {tool_name}: Erreur lecture fichier: {e}")
                return
            
            # Importer le module
            logger.info(f"🔧 {tool_name}: Création de la spec...")
            spec = importlib.util.spec_from_file_location(tool_name, tool_file)
            if spec is None:
                logger.error(f"❌ {tool_name}: Impossible de créer la spec du module")
                return
                
            logger.info(f"🔧 {tool_name}: Création du module...")
            module = importlib.util.module_from_spec(spec)
            if spec.loader is None:
                logger.error(f"❌ {tool_name}: Pas de loader disponible")
                return
            
            logger.info(f"🔧 {tool_name}: Exécution du module...")
            spec.loader.exec_module(module)
            logger.info(f"✅ {tool_name}: Module importé avec succès")
            
            # Lister tous les attributs du module pour debug
            logger.info(f"🔍 {tool_name}: Analyse du contenu du module...")
            all_members = inspect.getmembers(module)
            functions = [name for name, obj in all_members if inspect.isfunction(obj)]
            coroutines = [name for name, obj in all_members if inspect.iscoroutinefunction(obj)]
            
            logger.info(f"📋 {tool_name}: Fonctions trouvées: {functions}")
            logger.info(f"📋 {tool_name}: Coroutines trouvées: {coroutines}")
            
            # Chercher les fonctions d'outils
            tool_functions = self._find_tool_functions(module)
            
            if not tool_functions:
                logger.warning(f"⚠️  {tool_name}: Aucune fonction d'outil trouvée")
                logger.info(f"💡 {tool_name}: Essayez d'ajouter des fonctions async ou des fonctions avec 'tool' dans le nom")
                return
            
            # Sauvegarder l'outil
            self.loaded_tools[tool_name] = {
                "module": module,
                "functions": tool_functions,
                "function_objects": {name: func for name, func in tool_functions.items()}
            }
            
            logger.info(f"✅ {tool_name}: {len(tool_functions)} fonctions chargées: {list(tool_functions.keys())}")
            
        except ImportError as e:
            logger.error(f"❌ {tool_name}: Erreur d'import: {e}")
            logger.error(f"🔍 Détails: {traceback.format_exc()}")
        except SyntaxError as e:
            logger.error(f"❌ {tool_name}: Erreur de syntaxe: {e}")
            logger.error(f"🔍 Ligne {e.lineno}: {e.text}")
        except Exception as e:
            logger.error(f"❌ {tool_name}: Erreur lors du chargement: {e}")
            logger.error(f"🔍 Détails: {traceback.format_exc()}")
    
    def _find_tool_functions(self, module) -> Dict[str, Any]:
        """Trouve toutes les fonctions d'outils dans un module avec stratégie améliorée"""
        tool_functions = {}
        
        # Stratégie 1: Fonctions avec décorateur _mcp_tool
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and hasattr(obj, '_mcp_tool'):
                tool_functions[name] = obj
                logger.info(f"🎯 Fonction MCP trouvée: {name}")
        
        # Stratégie 2: Fonctions avec 'tool' dans le nom
        if not tool_functions:
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and 'tool' in name.lower():
                    tool_functions[name] = obj
                    logger.info(f"🎯 Fonction 'tool' trouvée: {name}")
        
        # Stratégie 3: Fonctions spécialisées (weather, etc.)
        if not tool_functions:
            keywords = ['weather', 'temperature', 'rain', 'forecast', 'sunny', 'air_quality', 'sunrise', 'sunset']
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj):
                    if any(keyword in name.lower() for keyword in keywords):
                        tool_functions[name] = obj
                        logger.info(f"🎯 Fonction spécialisée trouvée: {name}")
        
        # Stratégie 4: Toutes les fonctions publiques (pas de _ au début)
        if not tool_functions:
            for name, obj in inspect.getmembers(module):
                if (inspect.isfunction(obj) and 
                    not name.startswith('_') and 
                    name not in ['main', 'run', 'start', 'stop', 'init', 'setup']):
                    tool_functions[name] = obj
                    logger.info(f"🎯 Fonction publique trouvée: {name}")
        
        return tool_functions
    
    def get_all_tools(self) -> Dict[str, List[str]]:
        """Retourne tous les outils disponibles"""
        result = {}
        for tool_name, tool_info in self.loaded_tools.items():
            result[tool_name] = list(tool_info["functions"].keys())
        return result
    
    async def execute_tool(self, tool_name: str, function_name: str, parameters: Dict[str, Any]) -> Any:
        """Exécute une fonction d'un outil"""
        if tool_name not in self.loaded_tools:
            available_tools = list(self.loaded_tools.keys())
            raise ValueError(f"Outil '{tool_name}' non trouvé. Outils disponibles: {available_tools}")
        
        tool_info = self.loaded_tools[tool_name]
        
        if function_name not in tool_info["function_objects"]:
            available_functions = list(tool_info["function_objects"].keys())
            raise ValueError(f"Fonction '{function_name}' non trouvée dans l'outil '{tool_name}'. Fonctions disponibles: {available_functions}")
        
        function = tool_info["function_objects"][function_name]
        
        try:
            logger.info(f"🚀 Exécution: {tool_name}.{function_name} avec {parameters}")
            
            # Vérifier si c'est une fonction async
            if inspect.iscoroutinefunction(function):
                result = await function(**parameters)
            else:
                result = function(**parameters)
            
            logger.info(f"✅ Exécution réussie: {tool_name}.{function_name} -> {type(result)}")
            return result
            
        except TypeError as e:
            logger.error(f"❌ Erreur de paramètres pour {tool_name}.{function_name}: {e}")
            # Donner des informations sur la signature de la fonction
            sig = inspect.signature(function)
            expected_params = list(sig.parameters.keys())
            raise ValueError(f"Paramètres incorrects pour {function_name}. Attendu: {expected_params}, reçu: {list(parameters.keys())}")
        except Exception as e:
            logger.error(f"❌ Erreur d'exécution {tool_name}.{function_name}: {e}")
            logger.error(f"🔍 Détails: {traceback.format_exc()}")
            raise
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """Informations sur un outil spécifique"""
        if tool_name not in self.loaded_tools:
            return {}
        
        tool_info = self.loaded_tools[tool_name]
        functions_info = {}
        
        for func_name, func in tool_info["function_objects"].items():
            sig = inspect.signature(func)
            functions_info[func_name] = {
                "parameters": list(sig.parameters.keys()),
                "docstring": func.__doc__ or "Pas de documentation",
                "is_async": inspect.iscoroutinefunction(func)
            }
        
        return {
            "functions": list(tool_info["functions"].keys()),
            "functions_info": functions_info
        }
    
    async def shutdown_all(self):
        """Arrête tous les serveurs d'outils"""
        for tool_name, tool_info in self.loaded_tools.items():
            try:
                # Si le module a une fonction de nettoyage
                module = tool_info["module"]
                if hasattr(module, 'cleanup'):
                    if inspect.iscoroutinefunction(module.cleanup):
                        await module.cleanup()
                    else:
                        module.cleanup()
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
            "tools_directory": str(self.tools_directory.absolute()),
            "tool_names": list(self.loaded_tools.keys()),
            "python_path_includes_tools": str(self.tools_directory.absolute()) in sys.path
        }