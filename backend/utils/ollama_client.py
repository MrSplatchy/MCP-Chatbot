import httpx
import json
import logging
from typing import Dict, List, Any, Optional
import re

logger = logging.getLogger(__name__)

class OllamaChatClient:
    def __init__(self, model: str, host: str = "http://localhost:11434"):
        self.model = model
        self.base_url = host
        self.client = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def chat(self, messages: List[Dict[str, str]], available_tools: Dict[str, Any] = None):
        """Chat avec l'IA, qui peut utiliser des outils automatiquement"""
        
        # Use context manager if client not initialized
        if not self.client:
            async with self:
                return await self._process_chat(messages, available_tools)
        else:
            return await self._process_chat(messages, available_tools)

    async def _process_chat(self, messages: List[Dict[str, str]], available_tools: Dict[str, Any] = None):
        """Process the chat internally"""
        # Ajouter les outils dans le prompt système
        if available_tools:
            system_message = self._create_system_prompt(available_tools)
            # Check if there's already a system message
            if messages and messages[0].get("role") == "system":
                # Merge with existing system message
                messages[0]["content"] = system_message["content"] + "\n\n" + messages[0]["content"]
                full_messages = messages
            else:
                full_messages = [system_message] + messages
        else:
            full_messages = messages
        
        # Appeler l'IA
        response = await self._call_ollama(full_messages)
        
        # Vérifier si l'IA veut utiliser un outil
        if available_tools and self._has_tool_call(response):
            return await self._handle_tool_call(full_messages, response, available_tools)
        
        return response

    def _has_tool_call(self, response: str) -> bool:
        """Check if response contains a tool call"""
        return "<tool_call>" in response and "</tool_call>" in response

    def _create_system_prompt(self, available_tools: Dict[str, Any]) -> Dict[str, str]:
        """Créer le prompt système avec les outils disponibles"""
        tools_description = "Outils disponibles:\n"
        for tool_name, functions in available_tools.items():
            if isinstance(functions, list):
                tools_description += f"- {tool_name}: {', '.join(functions)}\n"
            else:
                tools_description += f"- {tool_name}: {functions}\n"
        
        prompt = f"""Tu es un assistant intelligent qui peut utiliser des outils.

{tools_description}

Pour utiliser un outil, écris exactement:
<tool_call>
{{"tool": "nom_outil", "function": "fonction", "parameters": {{"param": "valeur"}}}}
</tool_call>

Exemples:
- Pour la météo: <tool_call>{{"tool": "weather_tool", "function": "get_current_weather", "parameters": {{"location": "Paris"}}}}</tool_call>
- Pour calculer: <tool_call>{{"tool": "calculator", "function": "add", "parameters": {{"a": 5, "b": 3}}}}</tool_call>

Utilise les outils quand nécessaire, puis réponds naturellement à l'utilisateur."""
        
        return {"role": "system", "content": prompt}

    async def _call_ollama(self, messages: List[Dict[str, str]]) -> str:
        """Appeler l'API Ollama"""
        try:
            client = self.client or httpx.AsyncClient(timeout=60.0)
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model, 
                    "messages": messages, 
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            return result["message"]["content"]
        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP Ollama: {e}")
            return f"Erreur de connexion avec Ollama: {str(e)}"
        except Exception as e:
            logger.error(f"Erreur Ollama: {e}")
            return f"Erreur lors de l'appel à Ollama: {str(e)}"

    async def _handle_tool_call(self, messages: List[Dict[str, str]], response: str, available_tools: Dict[str, Any]) -> str:
        """Gérer l'appel d'outil et relancer l'IA"""
        try:
            # Extraire l'appel d'outil
            tool_calls = self._extract_tool_calls(response)
            
            if not tool_calls:
                return response
            
            # Execute the first tool call
            tool_call = tool_calls[0]
            
            # Import here to avoid circular imports
            from main import tool_manager
            
            if not tool_manager:
                return "Erreur: Gestionnaire d'outils non disponible"
            
            result = await tool_manager.execute_tool(
                tool_call["tool"],
                tool_call["function"],
                tool_call.get("parameters", {})
            )
            
            # Créer un nouveau message avec le résultat
            tool_result_message = {
                "role": "assistant", 
                "content": f"J'ai utilisé l'outil {tool_call['tool']}.{tool_call['function']} et voici le résultat:\n{result}\n\nLaisse-moi te donner une réponse claire:"
            }
            
            # Relancer l'IA avec le résultat
            final_messages = messages + [tool_result_message]
            final_response = await self._call_ollama(final_messages)
            
            return final_response
            
        except Exception as e:
            logger.error(f"Erreur outil: {e}")
            return f"Désolé, il y a eu une erreur avec l'outil: {str(e)}"

    def _extract_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Extraire les appels d'outils du texte"""
        tool_calls = []
        pattern = r'<tool_call>(.*?)</tool_call>'
        matches = re.findall(pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                tool_call = json.loads(match.strip())
                tool_calls.append(tool_call)
            except json.JSONDecodeError as e:
                logger.error(f"Erreur parsing tool call: {e}, content: {match}")
                continue
        
        return tool_calls

    async def test_connection(self) -> bool:
        """Test the connection to Ollama"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False