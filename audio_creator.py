import json
import os
from openai import OpenAI
import requests
import time

class HindiPrescriptionAudioGenerator:
    def __init__(self, openai_api_key, elevenlabs_api_key):
        """Initialize with API keys"""
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.elevenlabs_api_key = elevenlabs_api_key
        self.elevenlabs_endpoint = "https://api.elevenlabs.io/v1/text-to-speech"

    def generate_hindi_instructions(self, json_path):
        """Generate Hindi patient-friendly instructions from prescription analysis"""
        try:
            # Read the prescription analysis JSON
            with open(json_path, 'r') as f:
                prescription_data = json.load(f)

            # Create prompt for ChatGPT
            prompt = self._create_gpt_prompt(prescription_data)
            
            # Get response from ChatGPT
            response = self.openai_client.chat.completions.create(
                model="gpt-4",  # GPT-4 has better Hindi capabilities
                messages=[
                    {"role": "system", "content": """You are a caring doctor speaking to an uneducated Hindi-speaking patient. 
                    Write instructions in simple conversational Hindi (use Hindi script, not romanized).
                    Focus on:
                    1. How to identify each medicine (color, shape, size)
                    2. When and how to take it
                    3. Basic purpose
                    Use very simple Hindi words that an uneducated person would understand.
                    Avoid English terms except for medicine names.
                    Be warm and reassuring in tone."""},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            instructions = response.choices[0].message.content
            return instructions

        except Exception as e:
            print(f"Error generating instructions: {str(e)}")
            return None

    def create_audio(self, instructions, output_path, voice_id="21m00Tcm4TlvDq8ikWAM"):
        """Generate Hindi audio file using Eleven Labs API"""
        try:
            # Headers for ElevenLabs API
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }

            # Request body
            data = {
                "text": instructions,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.71,
                    "similarity_boost": 0.5,
                    "style": 0.0,
                    "speaker_boost": True
                }
            }

            # Make the API request
            response = requests.post(
                f"{self.elevenlabs_endpoint}/{voice_id}",
                json=data,
                headers=headers
            )

            # Check if request was successful
            if response.status_code == 200:
                # Save the audio file
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                return True
            else:
                print(f"Error from ElevenLabs API: {response.status_code}")
                print(response.text)
                return False

        except Exception as e:
            print(f"Error generating audio: {str(e)}")
            return False

    def _create_gpt_prompt(self, prescription_data):
        """Create a prompt for ChatGPT based on prescription data"""
        prompt = """Please explain the following medicines and their description to a Hindi-speaking patient. 
        Use simple conversational Hindi (in Devanagari script) that an uneducated person can understand:

        दवाइयों के बारे में समझाएं:
        """
        
        for med in prescription_data:
            prompt += f"\nदवाई: {med['medicine']}\n"
            prompt += f"मात्रा: {med['dosage']}\n"
            
        prompt += """\n
        कृपया हर दवाई के लिए बताएं:
        1. दवाई कैसी दिखती है (रंग, आकार)
        2. कितनी और कब लेनी है
        3. किस काम के लिए है
        
        सरल हिंदी में समझाएं, जैसे आप मरीज से बात कर रहे हों।"""
        return prompt

    def list_available_voices(self):
        """List all available voices from ElevenLabs"""
        try:
            headers = {
                "Accept": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            
            response = requests.get(
                "https://api.elevenlabs.io/v1/voices",
                headers=headers
            )
            
            if response.status_code == 200:
                voices = response.json()
                return voices
            else:
                print(f"Error fetching voices: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error listing voices: {str(e)}")
            return None

def main():
    # API Keys (better to use environment variables)
    openai_api_key = "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"
    elevenlabs_api_key = "sk_935e5c43628ddc19d908fd6fcf0070056e567e85fbeb54c9"

    # Initialize generator
    generator = HindiPrescriptionAudioGenerator(openai_api_key, elevenlabs_api_key)

    # Input and output paths
    json_path = "prescription_analysis.json"
    audio_output_path = "patient_instructions_hindi.mp3"

    try:
        # List available voices (optional)
        print("Available voices:")
        voices = generator.list_available_voices()
        if voices:
            for voice in voices.get('voices', []):
                print(f"Voice ID: {voice['voice_id']}, Name: {voice['name']}")

        # Generate Hindi instructions
        print("\nGenerating Hindi instructions...")
        instructions = generator.generate_hindi_instructions(json_path)
        
        if instructions:
            print("\nGenerated Hindi Instructions:")
            print("=" * 50)
            print(instructions)
            print("=" * 50)

            # Save instructions to text file (with UTF-8 encoding for Hindi)
            with open("patient_instructions_hindi.txt", "w", encoding='utf-8') as f:
                f.write(instructions)

            # Generate audio
            print("\nGenerating audio file...")
            if generator.create_audio(instructions, audio_output_path):
                print(f"\nAudio file created successfully: {audio_output_path}")
            else:
                print("\nFailed to create audio file")

        else:
            print("Failed to generate instructions")

    except Exception as e:
        print(f"Error in main process: {str(e)}")

if __name__ == "__main__":
    main()