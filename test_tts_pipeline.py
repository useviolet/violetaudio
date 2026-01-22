# from torch import device  # This line was shadowing the 'device' variable from the previous cell and has been removed.
from TTS.api import TTS
import torch # Ensure torch is imported to use torch.device

# Re-evaluate the device to ensure it's a string ('cuda' or 'cpu')
# We will use a new variable name to avoid any lingering shadowing issues with 'device'
target_device = "cuda" if torch.cuda.is_available() else "cpu"

# The TTS constructor does not accept a 'device' keyword argument.
# Instead, the model can be moved to the desired device after initialization.
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
tts.to(target_device) # Pass the device string directly to .to()

# generate speech by cloning a voice using default settings
tts.tts_to_file(text="It took me quite a long time to develop a voice, and now that I have it I'm not going to be silent.",
                file_path="output.wav",
                speaker_wav="/Users/user/Documents/Jarvis/violet/LJ037-0171.wav",
                language="en")