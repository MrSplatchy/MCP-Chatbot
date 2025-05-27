import os
import importlib
import sys
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

class ToolManager:
    def __init__(self, tools_directory: str = None):
        # Multiple ways to determine tools directory
        if tools_directory:
            # Explicit path provided
            self.tools_directory = Path(tools_directory)
        else:
            # Try different resolution methods
            self.tools_directory = self._resolve_tools_directory()
        
        # Ensure absolute path
        if not self.tools_directory.is_absolute():
            self.tools_directory = self.tools_directory.resolve()
            
        self.loaded_tools: Dict[str, Any] = {}
        self.tool_servers: Dict[str, Any] = {}
        
        logger.info(f"ToolManager initialized with tools directory: {self.tools_directory}")
    
    def _resolve_tools_directory(self) -> Path:
        """
        Resolve tools directory using multiple strategies
        """
        # Strategy 1: Environment variable
        env_path = os.getenv("TOOLS_DIRECTORY")
        if env_path:
            path = Path(env_path)
            if path.exists():
                logger.info(f"Using tools directory from environment: {path}")
                return path
        
        # Strategy 2: Relative to current working directory
        cwd_tools = Path.cwd() / "tools"
        if cwd_tools.exists():
            logger.info(f"Using tools directory relative to CWD: {cwd_tools}")
            return cwd_tools
        
        # Strategy 3: Relative to this file's location
        file_dir = Path(__file__).parent.parent  # Go up from utils/
        file_tools = file_dir / "tools"
        if file_tools.exists():
            logger.info(f"Using tools directory relative to project: {file_tools}")
            return file_tools
        
        # Strategy 4: Check if we're in a package structure
        # Look for tools directory in the same level as main.py
        for parent in Path(__file__).parents:
            potential_tools = parent / "tools"
            if potential_tools.exists() and (parent / "main.py").exists():
                logger.info(f"Found tools directory in project root: {potential_tools}")
                return potential_tools
        
        # Strategy 5: Default fallback
        default_path = Path("tools")
        logger.warning(f"Tools directory not found, using default: {default_path}")
        return default_path
    
    def _add_tools_to_python_path(self):
        """Add tools directory to Python path for imports"""
        tools_parent = str(self.tools_directory.parent)
        if tools_parent not in sys.path:
            sys.path.insert(0, tools_parent)
            logger.debug(f"Added to Python path: {tools_parent}")
    
    async def discover_and_load_tools(self):
        """Discover and load all MCP tools from the tools directory"""
        if not self.tools_directory.exists():
            logger.error(f"Tools directory does not exist: {self.tools_directory}")
            logger.info("Creating tools directory...")
            self.tools_directory.mkdir(parents=True, exist_ok=True)
            
            # Create __init__.py if it doesn't exist
            init_file = self.tools_directory / "__init__.py"
            if not init_file.exists():
                init_file.write_text("# Tools package\n")
            
            logger.warning("No tools found. Add tool files to the tools directory.")
            return
        
        # Add tools directory to Python path for imports
        self._add_tools_to_python_path()
        
        # Find all Python files in tools directory
        tool_files = [f for f in self.tools_directory.glob("*.py") 
                     if f.name != "__init__.py" and not f.name.startswith("_")]
        
        if not tool_files:
            logger.warning(f"No tool files found in {self.tools_directory}")
            return
        
        logger.info(f"Found {len(tool_files)} tool files: {[f.name for f in tool_files]}")
        
        for tool_file in tool_files:
            await self._load_tool(tool_file)
    
    async def _load_tool(self, tool_file: Path):
        """Load a single MCP tool"""
        try:
            # Dynamic import using the tools directory name
            tools_package = self.tools_directory.name
            module_name = f"{tools_package}.{tool_file.stem}"
            
            logger.debug(f"Importing module: {module_name}")
            
            # Remove from sys.modules if already loaded (for reloading)
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # Import the module
            module = importlib.import_module(module_name)
            
            # Get the MCP server from the module
            if hasattr(module, 'mcp_server'):
                server = module.mcp_server
                tool_name = tool_file.stem
                
                # Start the MCP server
                await server.start()
                
                # Store references
                self.tool_servers[tool_name] = server
                self.loaded_tools[tool_name] = {
                    "name": tool_name,
                    "server": server,
                    "tools": server.list_tools(),
                    "module": module,
                    "file_path": str(tool_file)
                }
                
                logger.info(f"✓ Loaded tool: {tool_name} with {len(server.list_tools())} functions")
                
            else:
                logger.warning(f"No 'mcp_server' found in {tool_file}")
                
        except Exception as e:
            logger.error(f"Failed to load tool from {tool_file}: {e}")
            logger.debug(f"Import error details:", exc_info=True)
    
    def get_tools_directory_info(self) -> Dict[str, Any]:
        """Get information about the tools directory"""
        return {
            "path": str(self.tools_directory),
            "absolute_path": str(self.tools_directory.absolute()),
            "exists": self.tools_directory.exists(),
            "is_directory": self.tools_directory.is_dir(),
            "tool_files": [f.name for f in self.tools_directory.glob("*.py") 
                          if f.name != "__init__.py"],
            "loaded_tools": list(self.loaded_tools.keys())
        }
    
    def get_all_tools(self) -> Dict[str, List[str]]:
        """Get all available tools grouped by tool server"""
        result = {}
        for tool_name, tool_info in self.loaded_tools.items():
            result[tool_name] = tool_info["tools"]
        return result
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """Get information about a specific tool server"""
        return self.loaded_tools.get(tool_name, {})
    
    async def execute_tool(self, tool_server_name: str, function_name: str, parameters: Dict[str, Any]):
        """Execute a specific function from a tool server"""
        if tool_server_name not in self.tool_servers:
            raise ValueError(f"Tool server '{tool_server_name}' not found")
        
        server = self.tool_servers[tool_server_name]
        return await server.call_tool(function_name, parameters)
    
    async def reload_tool(self, tool_name: str):
        """Reload a specific tool"""
        if tool_name in self.loaded_tools:
            # Stop the current server
            await self.tool_servers[tool_name].stop()
            
            # Remove from loaded tools
            tool_file_path = Path(self.loaded_tools[tool_name]["file_path"])
            del self.loaded_tools[tool_name]
            del self.tool_servers[tool_name]
            
            # Reload the tool
            await self._load_tool(tool_file_path)
            logger.info(f"Reloaded tool: {tool_name}")
        else:
            raise ValueError(f"Tool '{tool_name}' not found")
    
    async def shutdown_all(self):
        """Shutdown all loaded MCP servers"""
        for tool_name, server in self.tool_servers.items():
            try:
                await server.stop()
                logger.info(f"Shutdown tool: {tool_name}")
            except Exception as e:
                logger.error(f"Error shutting down {tool_name}: {e}")