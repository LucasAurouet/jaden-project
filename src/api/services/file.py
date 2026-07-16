import os
from fastapi import UploadFile
from typing import List, Dict, Any
from src.api.services.database import save_message

WORKSPACE_DIR = r"C:\Users\Lucas\Documents\maia"
ALLOWED_EXTENSIONS = {".txt", ".md", ".py", ".js", ".json", ".html", ".css", ".csv", ".xml", ".ini", ".yaml", ".yml"}
MAX_FILE_SIZE = 10 * 1024 * 1024 

class FileService:
    """
    Gère la persistance, le filtrage et la sécurité des documents du workspace de l'agent.
    """
    
    @staticmethod
    async def feed_file_to_session(file: UploadFile, session_id: str) -> Dict[str, Any]:
        """
        Lit le fichier binaire entrant, le décode en texte UTF-8,
        et l'enregistre directement dans l'historique de discussion SQLite.
        """
        raw_filename = file.filename
        clean_filename = os.path.basename(raw_filename)
        
        if not clean_filename:
            return {"status": "error", "message": "Nom de fichier invalide."}

        # 1. Vérification de l'extension
        _, ext = os.path.splitext(clean_filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            return {
                "status": "error", 
                "message": f"Format non pris en charge pour injection directe. Formats autorisés : {', '.join(ALLOWED_EXTENSIONS)}"
            }

        try:
            # 2. Lecture directe en mémoire (sans écriture disque)
            content_bytes = await file.read()
            total_size = len(content_bytes)

            # 3. Vérification de la taille pour préserver le contexte du LLM
            if total_size > MAX_FILE_SIZE:
                return {
                    "status": "error", 
                    "message": "Le fichier est trop volumineux pour être injecté directement dans le contexte (max 2 Mo)."
                }

            # 4. Décodage du fichier binaire en texte brut
            try:
                file_content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    # Fallback sur l'encodage Windows classique si l'UTF-8 échoue
                    file_content = content_bytes.decode("latin-1")
                except Exception:
                    return {
                        "status": "error", 
                        "message": "Impossible de décoder le fichier. Assurez-vous qu'il s'agit d'un fichier texte lisible."
                    }

            # 5. Création du bloc de contexte système pour le LLM
            system_prompt = (
                f"[SYSTEME : L'utilisateur vient de téléverser le fichier '{clean_filename}'. "
                f"Voici son contenu pour t'aider à répondre aux questions futures de l'utilisateur :\n\n"
                f"--- DÉBUT DU FICHIER : {clean_filename} ---\n"
                f"{file_content}\n"
                f"--- FIN DU FICHIER : {clean_filename} ---]"
            )

            # 6. Injection directe dans la DB SQLite pour cette session de chat
            save_message(session_id, "system", system_prompt)

            return {
                "status": "success",
                "message": f"Le fichier '{clean_filename}' a été lu et injecté dans le contexte de l'IA !",
                "filename": clean_filename,
                "characters_read": len(file_content)
            }

        except Exception as e:
            return {"status": "error", "message": f"Erreur lors de la lecture du fichier : {str(e)}"}
        

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
                stat = os.stat(file_path)
                files_list.append({
                    "name": filename,
                    "size": stat.st_size,
                    "modified": stat.st_mtime
                })
        return files_list