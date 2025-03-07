import os
import torch
import logging
import uvicorn
import soundfile as sf
import tempfile
import numpy as np
import subprocess
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, Response
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from cli.SparkTTS import SparkTTS
from sparktts.utils.token_parser import LEVELS_MAP_UI

# Initialize model once
MODEL_DIR = "pretrained_models/Spark-TTS-0.5B"
DEVICE = torch.device("cpu")
MODEL = SparkTTS(MODEL_DIR, DEVICE)

def convert_audio_to_wav(input_file, output_file, target_sr=16000):
    """Convert input audio (mp3/m4a) to WAV format at 16kHz using ffmpeg."""
    command = [
        "ffmpeg", "-i", input_file, "-y", "-ar", str(target_sr), "-ac", "1", "-f", "wav", output_file
    ]
    subprocess.run(command, check=True)
    return output_file

def run_tts(text, prompt_text=None, prompt_speech=None, gender=None, pitch=None, speed=None, save_dir="generated_audio", stream=False):
    """Generate TTS audio and return file path or streamed response."""
    os.makedirs(save_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    save_path = os.path.join(save_dir, f"{timestamp}.wav")

    with torch.no_grad():
        wav = MODEL.inference(text, prompt_speech, prompt_text, gender, pitch, speed)
        if isinstance(wav, np.ndarray):
            sf.write(save_path, wav, samplerate=16000)
        else:
            raise TypeError("Generated audio is not a valid NumPy array")

    if stream:
        def audio_stream():
            with open(save_path, "rb") as audio_file:
                yield from audio_file
        return save_path, StreamingResponse(audio_stream(), media_type="audio/wav")
    else:
        return save_path, FileResponse(save_path, media_type="audio/wav", filename=os.path.basename(save_path))

app = FastAPI()
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/voice_clone")
async def voice_clone(
    text: str = Form(...),
    prompt_text: str = Form(None),
    prompt_audio: UploadFile = File(None),
    pitch: int = Form(3),
    speed: int = Form(3),
    stream: bool = Form(False)
):
    """Voice cloning endpoint with proper audio file handling and conversion."""
    prompt_speech = None
    if prompt_audio:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
            temp_wav_path = temp_wav.name
            temp_wav.close()
            
            if prompt_audio.filename.endswith((".mp3", ".m4a")):
                with tempfile.NamedTemporaryFile(delete=False, suffix="." + prompt_audio.filename.split(".")[-1]) as temp_audio:
                    temp_audio.write(await prompt_audio.read())
                    temp_audio_path = temp_audio.name
                convert_audio_to_wav(temp_audio_path, temp_wav_path)
            else:
                with open(temp_wav_path, "wb") as f:
                    f.write(await prompt_audio.read())

        prompt_speech = temp_wav_path
    
    pitch_val = LEVELS_MAP_UI[pitch]
    speed_val = LEVELS_MAP_UI[speed]
    audio_path, response = run_tts(text, prompt_text, prompt_speech, pitch=pitch_val, speed=speed_val, stream=stream)
    return response

@app.post("/voice_create")
async def voice_create(
    text: str = Form(...),
    gender: str = Form("male"),
    pitch: int = Form(3),
    speed: int = Form(3),
    stream: bool = Form(False)
):
    """Voice creation endpoint."""
    pitch_val = LEVELS_MAP_UI[pitch]
    speed_val = LEVELS_MAP_UI[speed]
    audio_path, response = run_tts(text, gender=gender, pitch=pitch_val, speed=speed_val, stream=stream)
    return response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
