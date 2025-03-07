import os
import torch
import logging
import uvicorn
import soundfile as sf
import tempfile
import numpy as np
import subprocess
import base64
import json
from io import BytesIO
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, Response, Body, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from cli.SparkTTS import SparkTTS
from sparktts.utils.token_parser import LEVELS_MAP_UI

# Initialize model once
MODEL_DIR = "pretrained_models/Spark-TTS-0.5B"
DEVICE = torch.device("cpu")
MODEL = SparkTTS(MODEL_DIR, DEVICE)

# Models for OpenAI compatibility
class AudioContent(BaseModel):
    data: str  # Base64 encoded audio data
    format: str = "wav"

class InputAudio(BaseModel):
    input_audio: AudioContent

class ChatCompletionContentItem(BaseModel):
    type: str
    text: Optional[str] = None
    input_audio: Optional[AudioContent] = None

class ChatCompletionMessage(BaseModel):
    role: str
    content: Union[str, List[ChatCompletionContentItem]]

class AudioOptions(BaseModel):
    voice: str  # Required field that will be used for gender or voice clone indicator
    format: str = "wav"
    speed: Optional[int] = 3
    pitch: Optional[int] = 3

class ChatCompletionRequest(BaseModel):
    model: str
    modalities: List[str] = ["text", "audio"]
    audio: AudioOptions  # Required field
    messages: List[ChatCompletionMessage]

class AudioData(BaseModel):
    data: str  # Base64 encoded audio

class ResponseMessage(BaseModel):
    role: str = "assistant"
    content: str = ""
    audio: Optional[AudioData] = None

class Choice(BaseModel):
    index: int = 0
    message: ResponseMessage
    finish_reason: str = "stop"

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]

def convert_audio_to_wav(input_file, output_file, target_sr=16000):
    """Convert input audio (mp3/m4a) to WAV format at 16kHz using ffmpeg."""
    command = [
        "ffmpeg", "-i", input_file, "-y", "-ar", str(target_sr), "-ac", "1", "-f", "wav", output_file
    ]
    subprocess.run(command, check=True)
    return output_file

def run_tts(text, prompt_text=None, prompt_speech=None, gender=None, pitch=None, speed=None, save_dir="generated_audio", stream=False):
    """Generate TTS audio and return file path and audio data."""
    os.makedirs(save_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    save_path = os.path.join(save_dir, f"{timestamp}.wav")

    with torch.no_grad():
        wav = MODEL.inference(text, prompt_speech, prompt_text, gender, pitch, speed)
        if isinstance(wav, np.ndarray):
            sf.write(save_path, wav, samplerate=16000)
        else:
            raise TypeError("Generated audio is not a valid NumPy array")

    # Read the generated audio file
    with open(save_path, "rb") as audio_file:
        audio_data = audio_file.read()
    
    if stream:
        def audio_stream():
            with open(save_path, "rb") as audio_file:
                yield from audio_file
        return save_path, audio_data, StreamingResponse(audio_stream(), media_type="audio/wav")
    else:
        return save_path, audio_data, FileResponse(save_path, media_type="audio/wav", filename=os.path.basename(save_path))

def process_temp_audio(audio_data, format_hint="wav"):
    """Process base64 encoded audio data and save to a temporary file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format_hint}") as temp_audio:
        temp_audio.write(audio_data)
        temp_audio_path = temp_audio.name
    
    # Convert to WAV if not already
    if not format_hint.lower() == "wav":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
            temp_wav_path = temp_wav.name
            temp_wav.close()
        convert_audio_to_wav(temp_audio_path, temp_wav_path)
        return temp_wav_path
    
    return temp_audio_path

app = FastAPI()
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# original endpoints
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
    _, _, response = run_tts(text, prompt_text, prompt_speech, pitch=pitch_val, speed=speed_val, stream=stream)
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
    _, _, response = run_tts(text, gender=gender, pitch=pitch_val, speed=speed_val, stream=stream)
    return response

# Add OpenAI-compatible endpoint
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint that handles both TTS and speech recognition."""
    
    pitch = request.audio.pitch if request.audio and request.audio.pitch is not None else 3
    speed = request.audio.speed if request.audio and request.audio.speed is not None else 3
    pitch_val = LEVELS_MAP_UI[pitch]
    speed_val = LEVELS_MAP_UI[speed]
    
    is_voice_clone = False
    gender = "male"
    prompt_speech = None
    prompt_text = None
    
    voice_option = request.audio.voice
    
    # bakchodi
    if voice_option in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
        gender = "female" if voice_option in ["nova", "shimmer", "fable"] else "male"
    
    # Special case for voice cloning indicator
    elif voice_option == "clone":
        is_voice_clone = True
    
    last_message = request.messages[-1]
    
    text_content = ""
    if isinstance(last_message.content, str):
        text_content = last_message.content
    else:
        for item in last_message.content:
            if item.type == "text":
                text_content = item.text
            elif item.type == "input_audio" and item.input_audio:
                # Found audio input, switch to voice cloning mode regardless of voice setting
                is_voice_clone = True
                audio_data = base64.b64decode(item.input_audio.data)
                prompt_speech = process_temp_audio(audio_data, item.input_audio.format)
    

    if is_voice_clone and prompt_speech:
        _, audio_data, _ = run_tts(
            text_content, 
            prompt_text=prompt_text,
            prompt_speech=prompt_speech,
            pitch=pitch_val,
            speed=speed_val,
            stream=False
        )
    else:
        _, audio_data, _ = run_tts(
            text_content, 
            gender=gender,
            pitch=pitch_val,
            speed=speed_val,
            stream=False
        )
    
    # Create the response in OpenAI format
    response_message = ResponseMessage(
        content=text_content,
        audio=AudioData(data=base64.b64encode(audio_data).decode('utf-8'))
    )
    
    response = ChatCompletionResponse(
        id=f"chatcmpl-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        created=int(datetime.now().timestamp()),
        model=request.model,
        choices=[Choice(message=response_message)]
    )
    
    return response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)