#!/usr/bin/env python3
"""
Script de débogage pour tester le chargement des outils
Usage: python debug_tools.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Configuration du logging pour voir tous les détails
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Importer le ToolManager
try:
    from utils.tool_manager import ToolManager
except ImportError:
    print("❌ Erreur: Impossible d'importer ToolManager depuis utils.tool_manager")
    print("Vérifiez que le fichier utils/tool_manager.py existe")
    sys.exit(1)

async def main():
    print("🔍 === DEBUG TOOL MANAGER ===")
    print()
    
    # 1. Vérifications initiales
    print("📋 1. VÉRIFICATIONS INITIALES:")
    current_dir = Path(__file__).parent
    tools_dir = (current_dir / "tools").resolve()
    
    print(f"   Répertoire courant: {current_dir}")
    print(f"   Répertoire tools: {tools_dir}")
    print(f"   Dossier tools existe: {tools_dir.exists()}")
    
    if tools_dir.exists():
        try:
            files = list(tools_dir.glob("*.py"))
            print(f"   Fichiers .py trouvés: {len(files)}")
            for f in files:
                print(f"     - {f.name}")
        except Exception as e:
            print(f"   ❌ Erreur lors de la lecture: {e}")
    
    print()
    
    # 2. Test du ToolManager
    print("🔧 2. TEST DU TOOL MANAGER:")
    tool_manager = ToolManager("tools")
    
    print("   Initialisation: OK")
    print(f"   Répertoire configuré: {tool_manager.tools_directory}")
    print()
    
    # 3. Chargement des outils
    print("⚙️  3. CHARGEMENT DES OUTILS:")
    await tool_manager.load_all_tools()
    print()
    
    # 4. Résultats
    print("📊 4. RÉSULTATS:")
    stats = tool_manager.get_stats()
    print(f"   Outils chargés: {stats['tools_loaded']}")
    print(f"   Fonctions totales: {stats['total_functions']}")
    print(f"   Noms des outils: {stats['tool_names']}")
    print(f"   Manager prêt: {tool_manager.is_ready()}")
    print()
    
    # 5. Détails des outils
    if tool_manager.is_ready():
        print("🔍 5. DÉTAILS DES OUTILS:")
        all_tools = tool_manager.get_all_tools()
        for tool_name, functions in all_tools.items():
            print(f"   📦 {tool_name}:")
            info = tool_manager.get_tool_info(tool_name)
            for func_name in functions:
                func_info = info['functions_info'][func_name]
                async_marker = "(async)" if func_info['is_async'] else "(sync)"
                params = func_info['parameters']
                doc = func_info['docstring'][:50] + "..." if len(func_info['docstring']) > 50 else func_info['docstring']
                print(f"     - {func_name}{async_marker} -> {params}")
                print(f"       Doc: {doc}")
        print()
        
        # 6. Test d'exécution
        print("🚀 6. TEST D'EXÉCUTION:")
        test_executed = False
        
        for tool_name, functions in all_tools.items():
            for func_name in functions:
                try:
                    info = tool_manager.get_tool_info(tool_name)
                    func_info = info['functions_info'][func_name]
                    params = func_info['parameters']
                    
                    # Test avec différents types de fonctions
                    test_params = {}
                    
                    # Essayer d'exécuter une fonction simple sans paramètres
                    if len(params) == 0:
                        print(f"   🎯 Test de {tool_name}.{func_name}() sans paramètres...")
                        result = await tool_manager.execute_tool(tool_name, func_name, {})
                        print(f"   ✅ Résultat: {result}")
                        test_executed = True
                        break
                    
                    # Essayer avec des paramètres simples si on reconnaît le type
                    elif func_name == "add_numbers" and len(params) == 2:
                        print(f"   🎯 Test de {tool_name}.{func_name}(a=5, b=3)...")
                        result = await tool_manager.execute_tool(tool_name, func_name, {"a": 5, "b": 3})
                        print(f"   ✅ Résultat: {result}")
                        test_executed = True
                        break
                    
                    elif func_name == "simple_greeting" and "name" in params:
                        print(f"   🎯 Test de {tool_name}.{func_name}(name='Test')...")
                        result = await tool_manager.execute_tool(tool_name, func_name, {"name": "Test"})
                        print(f"   ✅ Résultat: {result}")
                        test_executed = True
                        break
                        
                except Exception as e:
                    print(f"   ❌ Erreur lors du test de {tool_name}.{func_name}: {e}")
            
            if test_executed:
                break
        
        if not test_executed:
            print("   ⚠️  Aucun test d'exécution effectué (pas de fonction compatible trouvée)")
    
    else:
        print("❌ 5. Aucun outil chargé - impossible de continuer les tests")
        print()
        print("💡 SUGGESTIONS:")
        print("   1. Vérifiez que le dossier 'tools/' existe")
        print("   2. Ajoutez des fichiers .py dans le dossier 'tools/'")
        print("   3. Vérifiez que vos fichiers contiennent des fonctions")
        print("   4. Regardez les logs ci-dessus pour les erreurs détaillées")
    
    print()
    print("✨ === FIN DU DEBUG ===")

if __name__ == "__main__":
    asyncio.run(main())