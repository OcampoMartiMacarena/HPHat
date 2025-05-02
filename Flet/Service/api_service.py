from fastapi import FastAPI, HTTPException
from .dialogue_generator import (
    generate_response_from_audio,
    AudioDialogueInput,
    GeminiTextResponse
)
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)


@app.post("/process-audio", response_model=GeminiTextResponse)
async def process_audio(dialogue: AudioDialogueInput):
    return generate_response_from_audio(dialogue)

