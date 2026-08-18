import speech_recognition as sr
import sys
from pathlib import Path

# Ensure stdout handles UTF-8 for Telugu script output
sys.stdout.reconfigure(encoding='utf-8')

def transcribe_wav(wav_path: Path):
    print(f"\n==================================================")
    print(f"Transcribing: {wav_path.name}")
    print(f"==================================================")
    r = sr.Recognizer()
    try:
        with sr.AudioFile(str(wav_path)) as source:
            print("Reading audio data...")
            audio_data = r.record(source)
            
            # 1. Attempt Telugu Transcription
            print("Transcribing in Telugu (te-IN)...")
            try:
                text_te = r.recognize_google(audio_data, language="te-IN")
                print(f"\n--- Telugu Transcription ---\n{text_te}\n")
            except sr.UnknownValueError:
                print("\n--- Telugu Transcription ---\n(Could not understand audio in Telugu)")
            except Exception as e:
                print(f"\n--- Telugu Transcription ---\nError: {e}")
                
            # 2. Attempt English (India) Transcription
            print("Transcribing in English (en-IN)...")
            try:
                text_en = r.recognize_google(audio_data, language="en-IN")
                print(f"\n--- English-IN Transcription ---\n{text_en}\n")
            except sr.UnknownValueError:
                print("\n--- English-IN Transcription ---\n(Could not understand audio in English)")
            except Exception as e:
                print(f"\n--- English-IN Transcription ---\nError: {e}")
                
    except Exception as e:
        print(f"Error reading audio file: {e}")

if __name__ == "__main__":
    scratch_dir = Path("C:/Users/Kaivalya/.gemini/antigravity/brain/bcc3d2fa-d475-4775-83f4-b224c5bccbd1/scratch")
    wav_files = list(scratch_dir.glob("*.wav"))
    if not wav_files:
        print("No WAV files found in scratch directory.")
        sys.exit(1)
        
    for wav_f in wav_files:
        transcribe_wav(wav_f)
