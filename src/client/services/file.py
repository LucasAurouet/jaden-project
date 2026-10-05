import os
import asyncio
from fastapi import UploadFile
from typing import Dict, Any
from config import WORKSPACE_DIR as _WORKSPACE_PATH
from src.client.services.database import save_attachment

WORKSPACE_DIR = str(_WORKSPACE_PATH)
ALLOWED_EXTENSIONS = {".txt", ".md", ".py", ".js", ".json", ".html", ".css", ".csv", ".xml", ".ini", ".yaml", ".yml"}
MAX_FILE_SIZE = 512 * 1024

IGNORE_DIRS = {
    "venv", ".venv", "env", ".env", 
    "__pycache__", ".git", "node_modules", 
    ".vscode", ".idea", "dist", "build"
}

IGNORE_FILES = {
    ".DS_Store", "desktop.ini", "thumbs.db"
}
IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd",
}

class FileService:
    """
    Gère la persistance, le filtrage et la sécurité des documents du workspace de l'agent.
    """
    
    @staticmethod
    async def feed_file_to_session(file: UploadFile, session_id: str) -> Dict[str, Any]:
        """
        Lit le fichier binaire entrant, le décode en texte UTF-8,
        et l'enregistre comme pièce jointe de la session.
        """
        raw_filename = file.filename
        clean_filename = os.path.basename(raw_filename)
        
        if not clean_filename:
            return {"status": "error", "message": "Nom de fichier invalide."}

        _, ext = os.path.splitext(clean_filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            return {
                "status": "error", 
                "message": f"Format non pris en charge pour injection directe. Formats autorisés : {', '.join(ALLOWED_EXTENSIONS)}"
            }

        try:
            content_bytes = await file.read()
            total_size = len(content_bytes)

            if total_size > MAX_FILE_SIZE:
                return {
                    "status": "error", 
                    "message": f"Le fichier est trop volumineux pour être injecté directement dans le contexte (max {MAX_FILE_SIZE // 1024} Ko)."
                }

            try:
                file_content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    file_content = content_bytes.decode("latin-1")
                except Exception:
                    return {
                        "status": "error", 
                        "message": "Impossible de décoder le fichier. Assurez-vous qu'il s'agit d'un fichier texte lisible."
                    }

            await asyncio.to_thread(save_attachment, session_id, clean_filename, file_content)

            return {
                "status": "success",
                "message": f"Le fichier '{clean_filename}' a été lu et injecté dans le contexte de l'IA !",
                "filename": clean_filename,
                "characters_read": len(file_content)
            }

        except Exception as e:
            return {
                "status": "error", 
                "message": f"Erreur lors de la lecture du fichier : {str(e)}"
            }
        

    @staticmethod
    def list_workspace_files() -> Dict[str, Any]:
        """
        Parcourt récursivement le répertoire de travail en une seule passe.
        Génère à la fois la liste plate des fichiers avec leurs métadonnées
        et l'arborescence textuelle (arbre ASCII) pour le prompt système du LLM,
        tout en respectant strictement les filtres d'exclusion définis.
        """
        if not os.path.exists(WORKSPACE_DIR):
            return {
                "status": "error",
                "files": [],
                "tree": "Workspace inexistant ou inaccessible."
            }
            
        files_list = []
        tree_lines = [" / (workspace)"]
        
        def build_and_list(current_dir: str, prefix: str = ""):
            try:
                entries = os.listdir(current_dir)
            except Exception:
                return
                
            valid_dirs = []
            valid_files = []
            
            for entry in entries:
                path = os.path.join(current_dir, entry)
                if os.path.isdir(path):
                    if entry not in IGNORE_DIRS and not entry.startswith('.'):
                        valid_dirs.append(entry)
                else:
                    if entry not in IGNORE_FILES and not entry.startswith('.'):
                        _, ext = os.path.splitext(entry.lower())
                        if ext not in IGNORE_EXTENSIONS:
                            valid_files.append(entry)
            
            valid_dirs.sort()
            valid_files.sort()
            
            all_entries = [(d, True) for d in valid_dirs] + [(f, False) for f in valid_files]
            count = len(all_entries)
            
            for i, (name, is_dir) in enumerate(all_entries):
                is_last = (i == count - 1)
                connector = "└── " if is_last else "├── "
                full_path = os.path.join(current_dir, name)
                
                if is_dir:
                    tree_lines.append(f"{prefix}{connector} {name}")
                    extension_prefix = "    " if is_last else "│   "
                    build_and_list(full_path, prefix + extension_prefix)
                else:
                    tree_lines.append(f"{prefix}{connector} {name}")
                    try:
                        stat = os.stat(full_path)
                        relative_path = os.path.relpath(full_path, WORKSPACE_DIR)
                        clean_relative_path = relative_path.replace(os.sep, '/')
                        
                        files_list.append({
                            "name": clean_relative_path,
                            "size": stat.st_size,
                            "modified": stat.st_mtime
                        })
                    except Exception:
                        continue
                        
        build_and_list(WORKSPACE_DIR)
        
        return {
            "status": "success",
            "files": files_list,
            "tree": "\n".join(tree_lines)
        }
