import os
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service():
    """Inicializa y retorna el cliente de la API de Google Drive."""
    # Buscar el archivo de credenciales en ubicaciones comunes (local y Render Secrets)
    creds_locations = [
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json"),
        "credentials.json",
        "/etc/secrets/credentials.json"
    ]
    
    creds_path = None
    for loc in creds_locations:
        if loc and os.path.exists(loc):
            creds_path = loc
            break
            
    if not creds_path:
        raise FileNotFoundError(
            "No se encontro el archivo credentials.json de Google Service Account. "
            "Asegúrate de que este en la raiz del proyecto o configurado en Render."
        )
    
    # Cargar credenciales de la Service Account
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def list_files_in_folder(folder_id: str):
    """Lista todos los archivos en una carpeta especifica de Google Drive."""
    try:
        service = get_drive_service()
        query = f"'{folder_id}' in parents and trashed = false"
        print(f"[GOOGLE DRIVE] Listando archivos en la carpeta ID: {folder_id}...")
        
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, md5Checksum)"
        ).execute()
        
        files = results.get('files', [])
        print(f"[GOOGLE DRIVE] Se encontraron {len(files)} archivos en Google Drive.")
        return files
    except Exception as e:
        print(f"[GOOGLE DRIVE] Error al listar archivos: {str(e)}")
        raise e

def download_file(file_id: str, dest_path: str, mime_type: str = None):
    """Descarga un archivo de Google Drive a una ruta local temporal, exportando formatos nativos de Google."""
    try:
        service = get_drive_service()
        
        # Si es un documento de Google Docs nativo, debemos exportarlo a un formato estándar
        if mime_type == 'application/vnd.google-apps.document':
            print(f"[GOOGLE DRIVE] Exportando Google Doc nativo a formato DOCX...")
            request = service.files().export_media(
                fileId=file_id,
                mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        elif mime_type == 'application/vnd.google-apps.presentation':
            print(f"[GOOGLE DRIVE] Exportando Google Slide nativo a formato PPTX...")
            request = service.files().export_media(
                fileId=file_id,
                mimeType='application/vnd.openxmlformats-officedocument.presentationml.presentation'
            )
        else:
            # Descarga binaria estándar para PDFs, archivos DOCX subidos sin conversión, TXT, etc.
            request = service.files().get_media(fileId=file_id)
            
        print(f"[GOOGLE DRIVE] Descargando archivo ID: {file_id} en {dest_path}...")
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            
        # Escribir el contenido descargado al disco local
        with open(dest_path, 'wb') as f:
            f.write(fh.getvalue())
            
        print(f"[GOOGLE DRIVE] Descarga completa exitosa para: {dest_path}")
        return True
    except Exception as e:
        print(f"[GOOGLE DRIVE] Error al descargar archivo: {str(e)}")
        raise e
