import os
import traceback
import base64
import threading
import re
from pydantic import BaseModel
from typing import Optional, List
import whisper
import google.generativeai as genai
from dotenv import load_dotenv
import uuid
import pygame
import edge_tts

# ===============================
# CONFIGURACIONES INICIALES
# ===============================
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY", "NO_API_KEY_FOUND"))
model = genai.GenerativeModel("models/gemini-1.5-flash")

# Cargar el modelo Whisper más ligero
print("🔀 Cargando modelo Whisper...")
whisper_model = whisper.load_model("tiny")  # Cambiado de "base" a "tiny" para mayor velocidad
print("✅ Modelo Whisper cargado")

# ===============================
# MODELOS DE DATOS
# ===============================
class AudioDialogueInput(BaseModel):
    AudioFilePath: str
    Language: Optional[str] = "es"

class GeminiTextResponse(BaseModel):
    result: str
    audio_base64: Optional[str] = None
    finalizado: Optional[bool] = False

class DialogueTurn(BaseModel):
    pregunta: str
    respuesta: str

class HatSession(BaseModel):
    historial: List[DialogueTurn] = []
    pregunta_actual: int = 0
    finalizado: bool = False
    casa_asignada: Optional[str] = None

# ===============================
# ESTADO EN MEMORIA TEMPORAL
# ===============================
hat_session = HatSession()

def reset_hat_session():
    """Reinicia la sesión del Sombrero Seleccionador"""
    global hat_session
    hat_session = HatSession()
    print("🔄 Sesión del Sombrero reiniciada")

# ===============================
# FUNCIONES DE AUDIO
# ===============================
def transcribe_with_whisper(audio_path: str) -> str:
    try:
        if not os.path.exists(audio_path):
            print(f"❌ Error: El archivo de audio no existe en {audio_path}")
            return "Error: Archivo de audio no encontrado"

        if os.path.getsize(audio_path) == 0:
            print(f"❌ Error: El archivo de audio está vacío: {audio_path}")
            return "Error: Archivo de audio vacío"

        print(f"🎧 Transcribiendo audio con Whisper: {audio_path}")
        print(f"📊 Tamaño del archivo: {os.path.getsize(audio_path)} bytes")

        # Optimización: Configuración más rápida para Whisper
        result = whisper_model.transcribe(
            audio_path,
            language="es",
            task="transcribe",
            fp16=False,
            verbose=False,
            initial_prompt="Esta es una conversación hablada en español.",
            temperature=0.0,  # Reducir aleatoriedad
            best_of=1,  # Reducir búsqueda
            beam_size=1  # Reducir búsqueda
        )

        texto = result["text"].strip()

        # Validación básica
        if len(texto) < 4:
            print("⚠️ Advertencia: Transcripción demasiado corta")
            return "Error: No se pudo entender el audio"

        # Limpieza de caracteres no latinos válidos
        texto = re.sub(r"[^\w\sáéíóúüñÁÉÍÓÚÜÑ¿¡]", "", texto)

        # Verificación de contenido español básico
        palabras_es = ["el", "la", "que", "es", "en", "por", "con"]
        if not any(p in texto.lower() for p in palabras_es):
            print("⚠️ Advertencia: Transcripción no parece válida")
            return "Error: La transcripción no parece válida"

        print(f"📝 Transcripción obtenida: {texto}")
        return texto

    except Exception as e:
        print("❌ Error general al transcribir el audio con Whisper:")
        traceback.print_exc()
        return "Error al transcribir el audio."

async def generar_audio(texto: str) -> Optional[str]:
    try:
        path = "respuesta_sombrero_actual.mp3"
        if os.path.exists(path):
            os.remove(path)

        print("🎙️ Generando audio con Edge-TTS...")
        communicate = edge_tts.Communicate(texto, voice="es-ES-AlvaroNeural")
        await communicate.save(path)
        print(f"✅ Audio guardado en: {path}")

        # Optimización: Reducir calidad del audio para menor tamaño
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        print(f"📦 Codificación base64 OK ({len(encoded)} bytes)")

        # Reproducir audio en segundo plano
        threading.Thread(target=reproducir_audio, args=(path,), daemon=True).start()
        return encoded
    except Exception as e:
        print("❌ Error al generar audio con Edge-TTS:")
        traceback.print_exc()
        return None

def reproducir_audio(path: str):
    def _play():
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.quit()
        except Exception as e:
            print("❌ Error al reproducir el audio:")
            traceback.print_exc()

    threading.Thread(target=_play, daemon=True).start()

# ===============================
# FLUJO PRINCIPAL
# ===============================
async def generate_response_from_audio(dialogue: AudioDialogueInput) -> GeminiTextResponse:
    global hat_session

    try:
        if not os.path.exists(dialogue.AudioFilePath):
            print(f"❌ Error: Archivo de audio no encontrado: {dialogue.AudioFilePath}")
            return GeminiTextResponse(result="Error: No se encontró el archivo de audio")

        if os.path.getsize(dialogue.AudioFilePath) == 0:
            print(f"❌ Error: Archivo de audio vacío: {dialogue.AudioFilePath}")
            return GeminiTextResponse(result="Error: El archivo de audio está vacío")

        texto_usuario = transcribe_with_whisper(dialogue.AudioFilePath)

        # Si la sesión está finalizada, reiniciamos y comenzamos una nueva
        if hat_session.finalizado:
            print("🔄 Iniciando nueva sesión después de veredicto previo")
            reset_hat_session()
            # Generamos la primera pregunta directamente
            prompt = (
                "Sos el Sombrero Seleccionador de Hogwarts. Es la primera pregunta para un nuevo estudiante. "
                "Generá una pregunta introductoria que me ayude a comenzar a entender su personalidad. "
                "La pregunta debe ser profunda y reveladora sobre sus valores y carácter.\n\n"
                "Respondé SOLO con la pregunta, sin introducciones ni descripciones adicionales."
            )
            response = model.generate_content(prompt)
            proxima_pregunta = response.text.strip()
            
            # Agregar la nueva pregunta al historial
            hat_session.historial.append(DialogueTurn(pregunta=proxima_pregunta, respuesta=""))
            hat_session.pregunta_actual += 1

            prompt_final = (
                "Sos el Sombrero Seleccionador. Respondé brevemente en forma hablada y sin descripciones ni asteriscos. "
                f"Preguntá: \"{proxima_pregunta}\" con una introducción misteriosa y amigable."
            )

            response = model.generate_content(prompt_final)
            resultado = response.text.strip()

            audio_base64 = await generar_audio(resultado)
            return GeminiTextResponse(result=resultado, audio_base64=audio_base64)

        # Guardar la respuesta actual en el historial
        if hat_session.pregunta_actual > 0:
            hat_session.historial[-1].respuesta = texto_usuario
            print(f"📝 Registrando respuesta para pregunta {hat_session.pregunta_actual}")

        if hat_session.pregunta_actual >= 5:  # Limitamos a 5 preguntas para mantener la conversación concisa
            print(f"🎯 Todas las preguntas respondidas ({len(hat_session.historial)} respuestas)")
            respuestas_formateadas = "\n".join([
                f"{i+1}. {turn.pregunta} → \"{turn.respuesta}\""
                for i, turn in enumerate(hat_session.historial)
            ])
            prompt = (
                f"Sos el Sombrero Seleccionador de Hogwarts. Estas fueron las respuestas del usuario:\n{respuestas_formateadas}\n"
                "Basándote en esto, decidí a qué casa pertenece: Gryffindor, Slytherin, Ravenclaw o Hufflepuff.\n"
                "IMPORTANTE: Debes elegir una de las cuatro casas sin importar qué tan claras o confusas sean las respuestas. "
                "Nunca digas que las respuestas son confusas o ilógicas. "
                "Usá tu intuición mágica para determinar la casa más adecuada.\n"
                "Respondé SOLO con el nombre de la casa y una breve justificación hablada."
            )
            response = model.generate_content(prompt)
            resultado = response.text.strip()
            hat_session.finalizado = True
            hat_session.casa_asignada = resultado

            audio_base64 = await generar_audio(resultado)
            return GeminiTextResponse(result=resultado, audio_base64=audio_base64, finalizado=True)

        # Generar pregunta contextual basada en el historial
        historial_formateado = "\n".join([
            f"{i+1}. {turn.pregunta} → \"{turn.respuesta}\""
            for i, turn in enumerate(hat_session.historial)
        ])
        
        # Prompt diferente para la primera pregunta
        if hat_session.pregunta_actual == 0:
            prompt = (
                "Sos el Sombrero Seleccionador de Hogwarts. Es la primera pregunta para un nuevo estudiante. "
                "Generá una pregunta introductoria que me ayude a comenzar a entender su personalidad. "
                "La pregunta debe ser profunda y reveladora sobre sus valores y carácter.\n\n"
                "Respondé SOLO con la pregunta, sin introducciones ni descripciones adicionales."
            )
        else:
            prompt = (
                "Sos el Sombrero Seleccionador de Hogwarts. Basándote en el historial de respuestas del estudiante, "
                "generá una pregunta única y relevante que me ayude a determinar su casa. "
                "La pregunta debe ser diferente a las anteriores y debe ayudarme a entender mejor su personalidad.\n\n"
                f"Historial de respuestas:\n{historial_formateado}\n\n"
                "Respondé SOLO con la pregunta, sin introducciones ni descripciones adicionales."
            )

        print("🧠 Prompt a Gemini:")
        print(prompt)

        response = model.generate_content(prompt)
        proxima_pregunta = response.text.strip()

        print("✅ Respuesta de Gemini:")
        print(proxima_pregunta)

        # Agregar la nueva pregunta al historial
        hat_session.historial.append(DialogueTurn(pregunta=proxima_pregunta, respuesta=""))
        hat_session.pregunta_actual += 1

        prompt_final = (
            "Sos el Sombrero Seleccionador. Respondé brevemente en forma hablada y sin descripciones ni asteriscos. "
            f"Preguntá: \"{proxima_pregunta}\" con una introducción misteriosa y amigable."
        )

        response = model.generate_content(prompt_final)
        resultado = response.text.strip()

        audio_base64 = await generar_audio(resultado)
        return GeminiTextResponse(result=resultado, audio_base64=audio_base64)

    except Exception as e:
        print("❌ Error procesando audio o respuesta:")
        traceback.print_exc()
        return GeminiTextResponse(result="Error al transcribir o procesar el audio.")
