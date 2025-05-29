import httpx
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class OllamaChatClient:
    def __init__(self, model: str, host: str = "http://localhost:11434"):
        self.model = model
        self.base_url = host

    async def chat(self, messages: List[Dict[str, str]], available_tools: Dict[str, Any] = None):
        """Chat avec l'IA, qui peut utiliser des outils automatiquement"""
        
        # Ajouter les outils dans le prompt système
        if available_tools:
            system_message = self._create_system_prompt(available_tools)
            full_messages = [system_message] + messages
        else:
            full_messages = messages
        
        # Appeler l'IA
        response = await self._call_ollama(full_messages)
        
        # Vérifier si l'IA veut utiliser un outil
        if available_tools and "<tool_call>" in response:
            return await self._handle_tool_call(full_messages, response)
        
        return response

    def _create_system_prompt(self, available_tools: Dict[str, Any]) -> Dict[str, str]:
        """Créer le prompt système avec les outils disponibles"""
        tools_description = "Outils disponibles:\n"
        for tool_name, functions in available_tools.items():
            tools_description += f"- {tool_name}: {', '.join(functions)}\n"
        
        prompt = f"""Tu es un assistant intelligent qui peut utiliser des outils.

{tools_description}

Pour utiliser un outil, écris exactement:
<tool_call>
{{"tool_server": "nom_outil", "function_name": "fonction", "parameters": {{"param": "valeur"}}}}
</tool_call>

Exemples:
- Pour la météo: <tool_call>{{"tool_server": "weather_tool", "function_name": "get_current_weather", "parameters": {{"location": "Paris"}}}}</tool_call>
- Pour calculer: <tool_call>{{"tool_server": "calculator", "function_name": "add", "parameters": {{"a": 5, "b": 3}}}}</tool_call>

Utilise les outils quand nécessaire, puis réponds naturellement à l'utilisateur."""
        
        return {"role": "system", "content": prompt}

    async def _call_ollama(self, messages: List[Dict[str, str]]) -> str:
        """Appeler l'API Ollama"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False}
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

    async def _handle_tool_call(self, messages: List[Dict[str, str]], response: str) -> str:
        """Gérer l'appel d'outil et relancer l'IA"""
        try:
            # Extraire l'appel d'outil
            start = response.find("<tool_call>") + len("<tool_call>")
            end = response.find("</tool_call>")
            tool_call_json = response[start:end].strip()
            tool_call = json.loads(tool_call_json)
            
            # Exécuter l'outil
            from main import tool_manager
            result = await tool_manager.execute_tool(
                tool_call["tool_server"],
                tool_call["function_name"],
                tool_call.get("parameters", {})
            )
            
            # Ajouter le résultat et relancer l'IA
            tool_result = {"role": "system", "content": f"Résultat: {result}"}
            final_response = await self._call_ollama(messages + [tool_result])
            
            return final_response
            
        except Exception as e:
            logger.error(f"Erreur outil: {e}")
            return f"Désolé, il y a eu une erreur avec l'outil: {str(e)}"