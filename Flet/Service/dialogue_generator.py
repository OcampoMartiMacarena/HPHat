import os
import traceback
from pydantic import BaseModel
from typing import Optional
import whisper
import google.generativeai as genai
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY", "NO_API_KEY_FOUND"))
model = genai.GenerativeModel("models/gemini-1.5-pro")

# Entrada desde el frontend
class AudioDialogueInput(BaseModel):
    AudioFilePath: str  # Ruta al archivo de audio WAV local
    Language: Optional[str] = "es"

# Respuesta generada
class GeminiTextResponse(BaseModel):
    result: str

# 🔊 Transcribir audio localmente con Whisper
def transcribe_with_whisper(audio_path: str) -> str:
    try:
        # Asegurar que FFmpeg esté en el PATH para Whisper
        ffmpeg_path = "C:\\ffmpeg\\ffmpeg-7.1.1-essentials_build\\bin"
        if ffmpeg_path not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + ffmpeg_path

        print(f"🎧 Transcribiendo audio con Whisper: {audio_path}")
        model = whisper.load_model("base")  # También podés usar "tiny", "small"
        result = model.transcribe(audio_path, language="es")
        texto = result["text"].strip()
        print(f"📝 Transcripción obtenida: {texto}")
        return texto

    except Exception as e:
        print("❌ Error al transcribir el audio con Whisper:")
        traceback.print_exc()
        return "Error al transcribir el audio."

# 🔁 Flujo completo: transcribir → preguntar a Gemini
def generate_response_from_audio(dialogue: AudioDialogueInput) -> GeminiTextResponse:
    try:
        texto = transcribe_with_whisper(dialogue.AudioFilePath)

        if "Error al transcribir" in texto:
            return GeminiTextResponse(result=texto)

        prompt = f"El usuario dijo: \"{texto}\". ¿Qué pensás de esto? Respondé en {dialogue.Language.upper()}."

        print("🧠 Prompt a Gemini:")
        print(prompt)

        response = model.generate_content(prompt)
        result = response.text.strip()

        print("✅ Respuesta de Gemini:")
        print(result)

        return GeminiTextResponse(result=result)

    except Exception as e:
        print("❌ Error procesando audio o respuesta:")
        traceback.print_exc()
        return GeminiTextResponse(result="Error al transcribir o procesar el audio.")
