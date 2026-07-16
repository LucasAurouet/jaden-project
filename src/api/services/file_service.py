import os
import shutil
from fastapi import UploadFile
from typing import List, Dict, Any

WORKSPACE_DIR = r"C:\Users\Lucas\Documents\maia"
ALLOWED_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 Mo max

class FileService:
    """
    Gère la persistance, le filtrage et la sécurité des documents du workspace de l'agent.
    """
    
    @staticmethod
    async def save_uploaded_file(file: UploadFile) -> Dict[str, Any]:
        """
        Nettoie, valide et écrit de manière sécurisée un fichier entrant sur le disque.
        """
        raw_filename = file.filename
        clean_filename = os.path.basename(raw_filename)
        
        if not clean_filename:
            return {"status": "error", "message": "Nom de fichier invalide."}

        # Validation de l'extension
        _, ext = os.path.splitext(clean_filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            return {
                "status": "error", 
                "message": f"Format non autorisé. Formats acceptés : {', '.join(ALLOWED_EXTENSIONS)}"
            }

        # Validation du chemin absolu (Protection contre le Path Traversal)
        destination_path = os.path.normpath(os.path.join(WORKSPACE_DIR, clean_filename))
        if not destination_path.lower().startswith(WORKSPACE_DIR.lower()):
            return {"status": "error", "message": "Tentative d'écriture illégale hors du workspace."}

        try:
            total_size = 0
            with open(destination_path, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):  # Morceaux de 1 Mo
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE:
                        buffer.close()
                        os.remove(destination_path)
                        return {"status": "error", "message": "Le fichier dépasse la limite de 10 Mo."}
                    buffer.write(chunk)
            
            return {
                "status": "success",
                "message": f"Fichier '{clean_filename}' correctement sauvegardé !",
                "filename": clean_filename,
                "bytes_saved": total_size
            }
        except Exception as e:
            return {"status": "error", "message": f"Erreur d'écriture : {str(e)}"}

    @staticmethod
    def list_workspace_files() -> List[Dict[str, Any]]:
        """
        Parcourt le répertoire de travail et liste les fichiers disponibles.
        """
        if not os.path.exists(WORKSPACE_DIR):
            return []
            
        files_list = []
        for filename in os.listdir(WORKSPACE_DIR):
            file_path = os.path.join(WORKSPACE_DIR, filename)
            if os.path.isfile(file_path):
                # Récupération des métadonnées basiques
                stat = os.stat(file_path)
                files_list.append({
                    "name": filename,
                    "size": stat.st_size,
                    "modified": stat.st_mtime
                })
        return files_list