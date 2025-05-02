import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wavfile
import flet as ft
import os
import httpx

class Presenter:
    def __init__(self, view):
        self.view = view
        self.is_recording = False
        self.fs = 44100
        self.channels = 1
        self.audio_frames = []
        self.output_file = "grabacion_real.wav"
        self.stream = None

    def _callback(self, indata, frames, time, status):
        if self.is_recording:
            self.audio_frames.append(indata.copy())

    async def start_recording(self):
        print("🎤 Comenzando a grabar...")
        self.audio_frames = []

        self.stream = sd.InputStream(
            samplerate=self.fs,
            channels=self.channels,
            callback=self._callback
        )
        self.stream.start()
        self.is_recording = True

        self.view.mic_button.icon = ft.Icons.PAUSE
        self.view.mic_button.tooltip = "Pausar grabación"
        self.view.mic_button.update()
        self.view.update()

    async def stop_recording(self):
        print("🛑 Deteniendo grabación...")

        if self.stream:
            self.stream.stop()
            self.stream.close()

        audio_data = np.concatenate(self.audio_frames)
        wavfile.write(self.output_file, self.fs, audio_data)

        # Enviamos el archivo directamente (por path)
        await self.send_to_api(self.output_file)

        self.view.mic_button.icon = ft.Icons.MIC
        self.view.mic_button.tooltip = "Iniciar grabación"
        self.view.mic_button.update()
        self.view.update()

        self.is_recording = False

    async def send_to_api(self, filepath):
        payload = {
            "AudioFilePath": filepath,
            "Language": "es"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/process-audio",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
                data = response.json()
                resultado = data.get("result", "Sin respuesta válida")

                print("🧠 Respuesta de Gemini:")
                print(resultado)

                

        except Exception as e:
            print(f"❌ Error al enviar a la API: {e}")

    async def capture_voice(self):
        if not self.is_recording:
            await self.start_recording()
        else:
            await self.stop_recording()
