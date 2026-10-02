"""Check that both validation-results documents are in the sealed documentation inventory."""
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'tools/esx'))
import doc_inventory
wanted = ['MITgcm_to_Python_port_verification/KPP_port_validation/KPP_VALIDATION_RESULTS.md',
          'MITgcm_to_Python_port_verification/GGL90_port_validation/GGL90_VALIDATION_RESULTS.md']
configured = json.loads((root / 'esx/project.json').read_text())['configuration_paths']
inventory = set(doc_inventory.paths(root))
missing = [name for name in wanted if name not in configured or name not in inventory]
print(json.dumps({'wanted': wanted, 'missing': missing, 'inventory_files': len(inventory)}))
sys.exit(1 if missing else 0)
