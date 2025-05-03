import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wavfile
import flet as ft
import httpx
import asyncio
import tempfile
import base64
import os
import logging
import traceback
from Service.dialogue_generator import generate_response_from_audio, AudioDialogueInput

logger = logging.getLogger(__name__)

class Presenter:
    def __init__(self, view):
        self.view = view
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.fs = 44100
        self.channels = 1
        self.output_file = os.path.join(tempfile.gettempdir(), "grabacion_real.wav")
        self.stop_loop = False

        # Ajustes calibrados tras test
        self.silence_threshold = 0.0001
        self.silence_duration = 0.5  # Aumentado para dar más tiempo de silencio
        self.min_speech_threshold = 0.0005  # Aumentado para ser más estricto con la detección de voz
        self.min_speech_duration = 0.3  # Aumentado para asegurar que es voz real

        # Seleccionar micrófono Razer
        self.selected_device = self.find_microphone_by_name("Razer Seiren Mini")

    def find_microphone_by_name(self, target_name="Razer Seiren Mini"):
        for idx, device in enumerate(sd.query_devices()):
            if target_name.lower() in device['name'].lower() and device['max_input_channels'] > 0:
                self.logger.info(f"✅ Usando micrófono: {device['name']} (ID: {idx})")
                return idx
        self.logger.warning(f"❌ No se encontró el micrófono '{target_name}', se usará el predeterminado.")
        return None

    async def grabar_hasta_silencio(self):
        self.logger.info("🎙️ Iniciando grabación...")
        try:
            if self.selected_device is not None:
                device_info = sd.query_devices(self.selected_device)
            else:
                device_info = sd.query_devices(kind='input')
            self.logger.info(f"🎤 Micrófono activo: {device_info['name']}")

            stream = sd.InputStream(
                device=self.selected_device,
                samplerate=self.fs,
                channels=self.channels,
                blocksize=int(self.fs * 0.01),
                dtype=np.float32
            )
            stream.start()
            self.logger.info("✅ Stream de audio iniciado correctamente")

            # Prueba rápida de energía inicial
            test_chunk, _ = stream.read(int(self.fs * 0.05))
            test_energy = np.sqrt(np.mean(test_chunk**2))
            self.logger.info(f"🔍 Prueba de energía inicial: {test_energy:.6f}")

            audio_buffer = []
            silencio_actual = 0
            voz_actual = 0
            chunk_size = int(self.fs * 0.01)
            alguien_hablo = False
            max_recording_time = 30
            recording_time = 0
            esperando_voz = True
            energia_promedio = 0
            muestras_energia = 0

            while recording_time < max_recording_time:
                chunk, overflowed = stream.read(chunk_size)
                if overflowed:
                    self.logger.warning("⚠️ Buffer desbordado")

                chunk = chunk.flatten().astype(np.float32)
                audio_buffer.append(chunk)

                energia = np.sqrt(np.mean(chunk**2))
                energia_promedio += energia
                muestras_energia += 1

                # Calcular umbral dinámico después de 1 segundo
                if recording_time >= 1.0 and muestras_energia > 0:
                    umbral_dinamico = (energia_promedio / muestras_energia) * 2
                    self.min_speech_threshold = max(umbral_dinamico, 0.0005)

                if energia > self.min_speech_threshold:
                    voz_actual += 0.01
                    silencio_actual = 0
                    if voz_actual >= self.min_speech_duration and not alguien_hablo:
                        self.logger.info(f"🗣️ Voz detectada (energía: {energia:.6f}, umbral: {self.min_speech_threshold:.6f})")
                        alguien_hablo = True
                        esperando_voz = False
                else:
                    voz_actual = 0
                    if alguien_hablo and not esperando_voz:
                        silencio_actual += 0.01
                        if silencio_actual >= self.silence_duration:
                            self.logger.info(f"🤫 Silencio detectado tras voz ({silencio_actual:.2f}s)")
                            break

                recording_time += 0.01

            stream.stop()
            stream.close()
            self.logger.info("🛑 Grabación detenida")

            if not alguien_hablo:
                self.logger.warning("❌ No se detectó voz")
                return None

            audio_data = np.concatenate(audio_buffer)
            self.logger.info(f"🔊 Tamaño del audio: {len(audio_data)} muestras")

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=tempfile.gettempdir())
            self.output_file = temp_file.name
            temp_file.close()

            # Guardar como int16 para Whisper
            audio_data = np.int16(audio_data * 32767)
            wavfile.write(self.output_file, self.fs, audio_data)

            self.logger.info(f"💾 Audio guardado en: {self.output_file} ({os.path.getsize(self.output_file)} bytes)")
            return self.output_file

        except Exception as e:
            self.logger.error(f"❌ Error durante la grabación: {e}")
            self.logger.error(traceback.format_exc())
            return None

    async def send_to_api(self, filepath):
        if filepath is None or not os.path.exists(filepath):
            self.logger.error("❌ Archivo de audio inválido o inexistente")
            return

        self.logger.info(f"📤 Enviando archivo: {filepath}")
        payload = {
            "AudioFilePath": filepath,
            "Language": "es"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:  # Aumentado el timeout
                response = await client.post(
                    "http://localhost:8000/process-audio",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
                self.logger.info(f"📥 Respuesta API: {response.status_code}")
                self.logger.info(response.text)

                if response.status_code != 200:
                    return

                data = response.json()
                resultado = data.get("result", "")
                audio_base64 = data.get("audio_base64")
                finalizado = data.get("finalizado", False)

                self.logger.info("🧠 Gemini respondió:")
                self.logger.info(resultado)

                # Intentar reproducir el audio pero continuar si falla
                if audio_base64:
                    try:
                        await self.reproducir_audio_base64(audio_base64)
                    except Exception as e:
                        self.logger.warning(f"⚠️ No se pudo reproducir el audio: {e}")
                        # Continuar con el diálogo aunque falle el audio

                if finalizado:
                    self.logger.info("🏁 Diálogo finalizado")
                    self.stop_loop = True
                    self.view.reset_microphone_state()
                    # Asegurarse de que el veredicto se muestre incluso si falla el audio
                    if resultado:
                        self.view.show_verdict(resultado)

        except httpx.ReadTimeout:
            self.logger.error("❌ Timeout al enviar a la API")
            # Si hay un timeout, intentar mostrar el veredicto de todos modos
            if resultado:
                self.logger.info("🏁 Mostrando veredicto final a pesar del timeout")
                self.stop_loop = True
                self.view.reset_microphone_state()
                self.view.show_verdict(resultado)
        except Exception as e:
            self.logger.error(f"❌ Error al enviar a la API: {e}")
            self.logger.error(traceback.format_exc())
            # Si hay un error, intentar mostrar el veredicto de todos modos
            if resultado:
                self.logger.info("🏁 Mostrando veredicto final a pesar del error")
                self.stop_loop = True
                self.view.reset_microphone_state()
                self.view.show_verdict(resultado)

    async def reproducir_audio_base64(self, base64_audio):
        try:
            audio_bytes = base64.b64decode(base64_audio)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
                temp_audio.write(audio_bytes)
                audio_path = temp_audio.name

            self.view.page.overlay.clear()
            self.view.page.overlay.append(ft.Audio(src=f"file://{audio_path}", autoplay=True))
            self.view.page.update()
            await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"❌ Error al reproducir audio: {e}")

    async def start_conversational_loop(self):
        self.logger.info("🔄 Iniciando bucle de conversación")
        self.stop_loop = False

        while not self.stop_loop:
            filepath = await self.grabar_hasta_silencio()
            if filepath:
                await self.send_to_api(filepath)
            else:
                self.logger.warning("⚠️ Grabación fallida, se intenta nuevamente")

        self.logger.info("🎩 Fin del diálogo del Sombrero")
        self.view.reset_microphone_state()
