"""Layout dos testes: monorepo (motor/) ou repositorio publico (plugins/<nome>/skills/<nome>/)."""
import os

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # motor/ ou plugins/<nome>/
_PUBLICO = os.path.join(PLUGIN, "skills", "leitor-de-notas-fiscais")

if os.path.exists(os.path.join(PLUGIN, "ler_notas.py")):
    SCRIPTS = PLUGIN  # ler_notas.py e engine/
    EXEMPLO = os.path.join(PLUGIN, "..", "venda", "fontes", "exemplo")
else:
    SCRIPTS = os.path.join(_PUBLICO, "scripts")
    EXEMPLO = os.path.join(_PUBLICO, "exemplo")
