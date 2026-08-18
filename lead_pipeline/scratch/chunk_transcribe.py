import sys
from pathlib import Path
from pydub import AudioSegment
import speech_recognition as sr
import static_ffmpeg

sys.stdout.reconfigure(encoding='utf-8')
static_ffmpeg.add_paths()

def transcribe_audio_chunks(wav_path: Path, chunk_length_ms=30000):
    print(f"\n==================================================")
    print(f"Detailed Chunked Transcription: {wav_path.name}")
    print(f"==================================================")
    
    try:
        # Load audio using pydub
        audio = AudioSegment.from_wav(str(wav_path))
        duration_sec = len(audio) / 1000.0
        print(f"Total Duration: {duration_sec:.2f} seconds ({duration_sec/60.0:.2f} minutes)")
        
        r = sr.Recognizer()
        
        # Split audio into chunks
        chunks = []
        for i in range(0, len(audio), chunk_length_ms):
            chunks.append(audio[i:i+chunk_length_ms])
            
        print(f"Split into {len(chunks)} chunks of {chunk_length_ms/1000}s each.\n")
        
        for idx, chunk in enumerate(chunks):
            start_sec = (idx * chunk_length_ms) / 1000.0
            end_sec = min(((idx + 1) * chunk_length_ms) / 1000.0, duration_sec)
            print(f"--- Chunk {idx+1}/{len(chunks)} ({start_sec:.1f}s - {end_sec:.1f}s) ---")
            
            # Export chunk to a temp wav file
            temp_wav_path = wav_path.parent / f"temp_chunk_{idx}.wav"
            chunk.export(str(temp_wav_path), format="wav")
            
            try:
                with sr.AudioFile(str(temp_wav_path)) as source:
                    audio_data = r.record(source)
                    
                    # Try Telugu
                    try:
                        text_te = r.recognize_google(audio_data, language="te-IN")
                        print(f"  [Telugu]: {text_te}")
                    except sr.UnknownValueError:
                        pass # No clear speech in this chunk
                    except Exception as e:
                        print(f"  [Telugu Error]: {e}")
                        
                    # Try English (India)
                    try:
                        text_en = r.recognize_google(audio_data, language="en-IN")
                        print(f"  [English-IN]: {text_en}")
                    except sr.UnknownValueError:
                        pass
                    except Exception as e:
                        print(f"  [English Error]: {e}")
            except Exception as e:
                print(f"  Error reading chunk {idx}: {e}")
            finally:
                # Clean up temp file
                if temp_wav_path.exists():
                    temp_wav_path.unlink()
                    
    except Exception as e:
        print(f"Error processing audio file: {e}")

if __name__ == "__main__":
    scratch_dir = Path("C:/Users/Kaivalya/.gemini/antigravity/brain/bcc3d2fa-d475-4775-83f4-b224c5bccbd1/scratch")
    wav_files = list(scratch_dir.glob("*.wav"))
    if not wav_files:
        print("No WAV files found in scratch directory.")
        sys.exit(1)
        
    for wav_f in wav_files:
        transcribe_audio_chunks(wav_f)
