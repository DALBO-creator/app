from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Form
from bson import ObjectId
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import PyPDF2
from PIL import Image
import base64
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import asyncio
from fastapi.responses import FileResponse
import aiofiles
import tempfile
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Utility function to prepare documents for MongoDB
def prepare_for_mongo(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = prepare_for_mongo(value)
            elif isinstance(value, list):
                data[key] = [prepare_for_mongo(item) if isinstance(item, dict) else item for item in value]
    return data

# Models
class DocumentUpload(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    content_type: str
    file_size: int
    extracted_text: Optional[str] = None
    summary_text: Optional[str] = None
    summary_type: Optional[str] = None  # "breve", "medio", "dettagliato"
    mindmap_schema: Optional[str] = None
    schema_type: Optional[str] = None  # "brainstorming", "cascata"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SummaryRequest(BaseModel):
    document_id: str
    summary_type: str  # "breve", "medio", "dettagliato"
    accuracy_level: str  # "standard", "alta"

class SchemaRequest(BaseModel):
    document_id: str
    schema_type: str  # "brainstorming", "cascata"

class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: Optional[str] = None
    message: str
    response: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChatRequest(BaseModel):
    document_id: Optional[str] = None
    message: str
    context: Optional[str] = None  # Testo del documento per contesto

# Helper functions
async def extract_text_from_pdf(file_content: bytes) -> str:
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logging.error(f"Error extracting PDF text: {e}")
        return ""

async def extract_text_with_gemini(file_path: str, mime_type: str) -> str:
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message="Sei un esperto nell'estrazione di testo da documenti. Estrai tutto il contenuto testuale dal documento fornito, mantenendo la struttura e l'ordine originale. Non omettere nessuna parte del contenuto."
        ).with_model("gemini", "gemini-2.0-flash")
        
        file_content = FileContentWithMimeType(
            file_path=file_path,
            mime_type=mime_type
        )
        
        user_message = UserMessage(
            text="Estrai tutto il testo da questo documento. Mantieni la struttura e l'ordine originale. Non omettere nessuna sezione, paragrafo o pagina.",
            file_contents=[file_content]
        )
        
        response = await chat.send_message(user_message)
        return response
    except Exception as e:
        logging.error(f"Error extracting text with Gemini: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nell'estrazione del testo: {str(e)}")

async def generate_summary_with_gemini(text: str, summary_type: str, accuracy_level: str) -> str:
    try:
        # Configurazione prompt basata sul tipo di riassunto
        length_instructions = {
            "breve": "Crea un riassunto molto conciso di massimo 200 parole",
            "medio": "Crea un riassunto di lunghezza media tra 300-500 parole",
            "dettagliato": "Crea un riassunto dettagliato e completo di 600-800 parole"
        }
        
        accuracy_instructions = {
            "standard": "Mantieni le informazioni principali",
            "alta": "Mantieni tutti i dettagli importanti, dati, cifre e punti chiave senza omettere nulla di rilevante"
        }
        
        system_message = f"""
Sei un esperto nella creazione di riassunti. {length_instructions.get(summary_type, length_instructions['medio'])}.
{accuracy_instructions.get(accuracy_level, accuracy_instructions['standard'])}.

Il riassunto deve:
- Catturare tutti i punti principali del documento
- Mantenere la logica e la struttura del testo originale
- Essere chiaro e ben organizzato
- Includere tutte le sezioni importanti del documento originale
"""
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message=system_message
        ).with_model("gemini", "gemini-2.0-flash")
        
        user_message = UserMessage(
            text=f"Crea un riassunto del seguente testo:\n\n{text}"
        )
        
        response = await chat.send_message(user_message)
        return response
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nella generazione del riassunto: {str(e)}")

async def generate_schema_with_gemini(text: str, schema_type: str) -> str:
    try:
        schema_instructions = {
            "brainstorming": "Crea una mappa mentale in formato testuale con le idee principali, concetti chiave e collegamenti. Usa simboli, frecce e indentazione per mostrare le relazioni.",
            "cascata": "Crea uno schema a cascata/flow chart che mostri la sequenza logica, i processi e i collegamenti gerarchici del contenuto. Usa frecce e livelli per mostrare il flusso."
        }
        
        system_message = f"""
Sei un esperto nella creazione di schemi e mappe mentali. {schema_instructions.get(schema_type, schema_instructions['brainstorming'])}

Lo schema deve:
- Essere visivamente chiaro e ben strutturato
- Mostrare tutte le relazioni importanti
- Usare simboli ASCII per migliorare la leggibilità
- Essere esportabile e comprensibile
"""
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message=system_message
        ).with_model("gemini", "gemini-2.0-flash")
        
        user_message = UserMessage(
            text=f"Crea uno schema {schema_type} del seguente contenuto:\n\n{text}"
        )
        
        response = await chat.send_message(user_message)
        return response
    except Exception as e:
        logging.error(f"Error generating schema: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nella generazione dello schema: {str(e)}")

async def create_pdf_export(content: str, title: str) -> str:
    """Crea un PDF da testo e ritorna il path del file"""
    try:
        # Crea file temporaneo
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        
        doc = SimpleDocTemplate(temp_file.name, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Aggiungi titolo
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
        )
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 12))
        
        # Aggiungi contenuto
        content_style = ParagraphStyle(
            'CustomContent',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
        )
        
        # Dividi il contenuto in paragafi
        paragraphs = content.split('\n')
        for para in paragraphs:
            if para.strip():
                story.append(Paragraph(para, content_style))
                story.append(Spacer(1, 6))
        
        doc.build(story)
        temp_file.close()
        
        return temp_file.name
    except Exception as e:
        logging.error(f"Error creating PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nella creazione del PDF: {str(e)}")

# API Routes


@api_router.post("/upload", response_model=dict)
async def upload_document(file: UploadFile = File(...)):
    try:
        # Verifica dimensione file (max 100MB)
        contents = await file.read()
        if len(contents) > 100 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File troppo grande. Massimo 100MB.")
        
        # Crea documento
        document = DocumentUpload(
            filename=file.filename,
            content_type=file.content_type,
            file_size=len(contents)
        )
        
        # Estrai testo
        extracted_text = ""
        
        if file.content_type == "application/pdf":
            # Prova prima con PyPDF2
            extracted_text = await extract_text_from_pdf(contents)
            
            # Se PyPDF2 non estrae testo (PDF scansionato), usa Gemini
            if not extracted_text or len(extracted_text.strip()) < 50:
                # Salva temporaneamente il file per Gemini
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                temp_file.write(contents)
                temp_file.close()
                
                extracted_text = await extract_text_with_gemini(temp_file.name, "application/pdf")
                os.unlink(temp_file.name)
        
        elif file.content_type.startswith("image/"):
            # Salva temporaneamente l'immagine per Gemini
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(contents)
            temp_file.close()
            
            extracted_text = await extract_text_with_gemini(temp_file.name, file.content_type)
            os.unlink(temp_file.name)
        
        else:
            raise HTTPException(status_code=400, detail="Tipo di file non supportato. Usa PDF o immagini.")
        
        if not extracted_text:
            raise HTTPException(status_code=400, detail="Impossibile estrarre testo dal documento.")
        
        document.extracted_text = extracted_text
        
        # Salva nel database
        document_dict = prepare_for_mongo(document.dict())
        result = await db.documents.insert_one(document_dict)
        
        return {
            "id": document.id,
            "filename": document.filename,
            "extracted_text": document.extracted_text[:500] + "..." if len(document.extracted_text) > 500 else document.extracted_text,
            "text_length": len(document.extracted_text),
            "message": "Documento caricato e analizzato con successo"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Errore durante il caricamento: {str(e)}")

@api_router.post("/generate-summary")
async def generate_summary(request: SummaryRequest):
    try:
        # Recupera documento
        document = await db.documents.find_one({"id": request.document_id})
        if not document:
            raise HTTPException(status_code=404, detail="Documento non trovato")
        
        if not document.get('extracted_text'):
            raise HTTPException(status_code=400, detail="Testo non disponibile per questo documento")
        
        # Genera riassunto
        summary = await generate_summary_with_gemini(
            document['extracted_text'],
            request.summary_type,
            request.accuracy_level
        )
        
        # Aggiorna documento
        await db.documents.update_one(
            {"id": request.document_id},
            {"$set": {
                "summary_text": summary,
                "summary_type": request.summary_type,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "document_id": request.document_id,
            "summary": summary,
            "summary_type": request.summary_type,
            "accuracy_level": request.accuracy_level
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Summary generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nella generazione del riassunto: {str(e)}")

@api_router.post("/generate-schema")
async def generate_schema(request: SchemaRequest):
    try:
        # Recupera documento
        document = await db.documents.find_one({"id": request.document_id})
        if not document:
            raise HTTPException(status_code=404, detail="Documento non trovato")
        
        if not document.get('extracted_text'):
            raise HTTPException(status_code=400, detail="Testo non disponibile per questo documento")
        
        # Genera schema
        schema = await generate_schema_with_gemini(
            document['extracted_text'],
            request.schema_type
        )
        
        # Aggiorna documento
        await db.documents.update_one(
            {"id": request.document_id},
            {"$set": {
                "mindmap_schema": schema,
                "schema_type": request.schema_type,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "document_id": request.document_id,
            "schema": schema,
            "schema_type": request.schema_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Schema generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nella generazione dello schema: {str(e)}")

@api_router.post("/chat", response_model=dict)
async def chat_with_document(request: ChatRequest):
    try:
        system_message = "Sei un assistente AI specializzato nell'aiutare gli utenti con documenti e contenuti. Puoi rispondere a domande, suggerire modifiche, e fornire supporto."
        
        # Se c'è un document_id, aggiungi il contesto del documento
        if request.document_id:
            document = await db.documents.find_one({"id": request.document_id})
            if document and document.get('extracted_text'):
                system_message += f"\n\nContesto del documento: {document['extracted_text'][:2000]}..."
        
        # Se c'è contesto aggiuntivo, aggiungilo
        if request.context:
            system_message += f"\n\nContesto aggiuntivo: {request.context}"
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message=system_message
        ).with_model("gemini", "gemini-2.0-flash")
        
        user_message = UserMessage(text=request.message)
        response = await chat.send_message(user_message)
        
        # Salva conversazione
        chat_message = ChatMessage(
            document_id=request.document_id,
            message=request.message,
            response=response
        )
        
        chat_dict = prepare_for_mongo(chat_message.dict())
        await db.chat_messages.insert_one(chat_dict)
        
        return {
            "message": request.message,
            "response": response,
            "chat_id": chat_message.id
        }
        
    except Exception as e:
        logging.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nella chat: {str(e)}")

@api_router.get("/export-pdf/{document_id}")
async def export_pdf(document_id: str, content_type: str = "summary"):
    try:
        document = await db.documents.find_one({"id": document_id})
        if not document:
            raise HTTPException(status_code=404, detail="Documento non trovato")
        
        if content_type == "summary":
            content = document.get('summary_text')
            title = f"Riassunto - {document.get('filename', 'Documento')}"
        elif content_type == "schema":
            content = document.get('mindmap_schema')
            title = f"Schema - {document.get('filename', 'Documento')}"
        elif content_type == "full":
            content = document.get('extracted_text')
            title = f"Testo Completo - {document.get('filename', 'Documento')}"
        else:
            raise HTTPException(status_code=400, detail="Tipo di contenuto non valido")
        
        if not content:
            raise HTTPException(status_code=400, detail="Contenuto non disponibile")
        
        pdf_path = await create_pdf_export(content, title)
        
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"{title}.pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"PDF export error: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nell'esportazione PDF: {str(e)}")

@api_router.get("/documents")
async def get_documents():
    try:
        documents = await db.documents.find().to_list(1000)
        return [
            {
                "id": doc["id"],
                "filename": doc["filename"],
                "content_type": doc["content_type"],
                "file_size": doc["file_size"],
                "has_summary": bool(doc.get("summary_text")),
                "has_schema": bool(doc.get("mindmap_schema")),
                "created_at": doc["created_at"],
                "text_preview": doc.get("extracted_text", "")[:200] + "..." if doc.get("extracted_text") else None
            }
            for doc in documents
        ]
    except Exception as e:
        logging.error(f"Get documents error: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nel recupero documenti: {str(e)}")

@api_router.get("/document/{document_id}")
async def get_document(document_id: str):
    try:
        document = await db.documents.find_one({"id": document_id})
        if not document:
            raise HTTPException(status_code=404, detail="Documento non trovato")
        
        return {
            "id": document["id"],
            "filename": document["filename"],
            "content_type": document["content_type"],
            "file_size": document["file_size"],
            "extracted_text": document.get("extracted_text"),
            "summary_text": document.get("summary_text"),
            "summary_type": document.get("summary_type"),
            "mindmap_schema": document.get("mindmap_schema"),
            "schema_type": document.get("schema_type"),
            "created_at": document["created_at"],
            "updated_at": document.get("updated_at")
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Get document error: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nel recupero documento: {str(e)}")

# --- NUOVO ENDPOINT DELETE ---
@api_router.delete("/document/{document_id}")
async def delete_document(document_id: str):
    """
    Elimina un documento dal database utilizzando il suo ID (stringa UUID).
    """
    try:
        # Trova e rimuove il documento usando il campo "id"
        result = await db.documents.delete_one({"id": document_id})

        # Controlla se l'eliminazione ha avuto successo
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Documento non trovato.")
        
        # Ritorna una risposta di successo
        return {"message": f"Documento {document_id} eliminato con successo."}

    except HTTPException:
        # Rilancia le eccezioni HTTP come 404
        raise
    except Exception as e:
        # Gestisce altri errori imprevisti
        logging.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Errore durante l'eliminazione: {str(e)}")

# --- FINE NUOVO ENDPOINT DELETE ---


@api_router.get("/")
async def root():
    return {"message": "DocBrains API - Analisi Documenti con AI"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
