"""Empaqueta el proyecto sin credenciales ni caches."""
from pathlib import Path
import zipfile

root=Path(__file__).resolve().parents[1]
destination=root.parent/'maximiliano-estudiante.zip'
excluded={'.env','credenciales.txt','__pycache__','.git'}
with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
    for file in root.rglob('*'):
        relative=file.relative_to(root)
        if file.is_file() and not any(p in excluded for p in relative.parts) and file.suffix!='.log':
            archive.write(file,Path(root.name)/relative)
print(destination)
