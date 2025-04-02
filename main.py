from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, TextClip, concatenate_audioclips
from moviepy.video.tools.subtitles import SubtitlesClip
from moviepy.config import change_settings
from moviepy.video.fx import all as vfx
from PIL import Image, ImageDraw, ImageFont
from utils.box import make_title_box
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
import google.auth.transport.requests
import google_auth_oauthlib.flow
import numpy as np
import pickle
import whisper
import os
import random
import json
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

imagemagic_path = r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"
change_settings({"IMAGEMAGICK_BINARY": imagemagic_path})

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = os.getenv("CLIENT_SECRET_PATH")
SPEECHIFY_API_KEY = os.getenv("SPEECHIFY_API_KEY")
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

model = whisper.load_model("medium.en", device="cuda") 

def authenticate_youtube():
    credentials = None

    if os.path.exists("utils/token.pickle"):
        with open("utils/token.pickle", "rb") as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("Refreshing expired credentials...")
            credentials.refresh(google.auth.transport.requests.Request()) 
        else:
            print("OAuth flow initiated...")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES)
            credentials = flow.run_local_server()

        with open("utils/token.pickle", "wb") as token:
            pickle.dump(credentials, token)

    youtube = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
    return youtube

def generate_tts(title, text, gender):
    url = "https://api.sws.speechify.com/v1/audio/speech"
    voice = "lisa" if gender == "female" else "joe"
    
    headers = {
        "Authorization": f"Bearer {SPEECHIFY_API_KEY}",
        "Content-Type": "application/json"
    }

    def get_audio(input_text, filename):
        payload = {
            "input": input_text,
            "voice_id": voice,
            "format": "mp3"
        }
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            try:
                response_json = response.json()
                if "audio_data" not in response_json:
                    print(f"Error: Missing 'audio_data' in response: {response_json}")
                    return None
                
                # Decode base64 audio data
                audio_data = base64.b64decode(response_json["audio_data"])

                # Save as MP3 file
                with open(filename, 'wb') as f:
                    f.write(audio_data)

                print(f"TTS generated successfully: {filename}")
                return filename
            except Exception as e:
                print(f"Error decoding response: {e}")
                return None
        else:
            print(f"API Error: {response.status_code} - {response.text}")
            return None

    title_filename = "title_audio.mp3"
    text_filename = "story_audio.mp3"

    title_file = get_audio(title, title_filename)
    text_file = get_audio(text, text_filename)

    return title_file, text_file

def get_video_number():
    filename = 'utils/counter.txt'

    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            f.write('0')

    with open(filename, 'r') as f:
        count = int(f.read().strip())

    count += 1

    with open(filename, 'w') as f:
        f.write(str(count))

    return count

def add_text_glow(text, font, size, color, glow_radius=5):
    img = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    bbox = draw.textbbox((0, 0), text, font=font)
    x_center = (size[0] - (bbox[2] - bbox[0])) // 2
    y_center = (size[1] - (bbox[3] - bbox[1])) // 2
    
    for dx in range(-glow_radius, glow_radius + 1, 2):
        for dy in range(-glow_radius, glow_radius + 1, 2):
            draw.text((x_center + dx, y_center + dy), text, font=font, fill=(0, 0, 0, 150))
    draw.text((x_center, y_center), text, font=font, fill=color)
    return img

def create_text_with_glow(text, fontsize, color, font_path, size=(900, 200), glow_radius=5):
    font = ImageFont.truetype(font_path, fontsize)
    pil_image = add_text_glow(text, font, size, color, glow_radius)
    return ImageClip(np.array(pil_image)).set_duration(5).set_fps(24).resize(height=size[1])


def generate_video(file_path, cropped=True):
    print("Starting video generation...")

    title_audio = AudioFileClip("title_audio.mp3")
    story_audio = AudioFileClip("story_audio.mp3")

    background_video = VideoFileClip("utils/gameplay.mp4")

    title_duration = title_audio.duration
    story_start_time = title_duration

    total_duration = title_audio.duration + story_audio.duration
    seed = random.uniform(0, 60*60 - total_duration - 60)
    background_video = background_video.subclip(seed, seed + total_duration)

    if cropped:
        if background_video.h < 1920:
            background_video = background_video.resize(height=1920)

        background_video = background_video.crop(width=1080, height=1920, x_center=background_video.w // 2, y_center=background_video.h // 2)

    print("Creating image clip for title...")

    original_width = 485
    original_height = 175
    new_width = 880
    new_height = int((new_width / original_width) * original_height)

    image_clip = ImageClip("utils/output_image.png").resize(width=new_width, height=new_height)
    image_clip = image_clip.set_position('center').set_duration(title_duration)  

    print("Generating subtitles using Whisper...")
 
    result = model.transcribe("story_audio.mp3", word_timestamps=True)

    subtitles = []
    story_end_time = title_duration + story_audio.duration 

    for segment in result['segments']:
        for word in segment['words']:
            start_time = word['start'] + title_duration  
            end_time = word['end'] + title_duration 
            text = word['word']  

            solid_caption = create_text_with_glow(
                text,  
                fontsize=100,
                color="white",  
                font_path="utils/Montserrat-ExtraBold.ttf",  
                glow_radius=5  
            ).set_position(("center", "center")).set_start(start_time).set_duration(end_time - start_time)

            subtitles.append(solid_caption)

    print("Merging audio...")
    combined_audio = concatenate_audioclips([title_audio, story_audio.set_start(story_start_time)])

    background_video = background_video.set_audio(combined_audio)

    print("Composing final video...")
    final_video = CompositeVideoClip([background_video, image_clip] + subtitles)

    final_video = final_video.set_duration(total_duration)

    print("Saving final video as 'Final_video_with_captions.mp4'...")

    final_video.write_videofile(file_path, codec='libx265', audio_codec='aac', bitrate="10000k",  audio_bitrate="320k", threads=12)

    print("Final Video Completed!")

def upload_video(youtube, video_file, title, description, tags, category="22", privacy="public"):
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category
        },
        "status": {
            "privacyStatus": privacy  
        }
    }

    media_file = MediaFileUpload(video_file, chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media_file
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploading... {int(status.progress() * 100)}%")
    print("Video uploaded successfully.")
    print(f"Video ID: {response['id']}")

def cleanup():
    os.remove("story_audio.mp3")
    os.remove("title_audio.mp3")
    os.remove("utils/output_image.png")


def load_story(count):
    with open("utils/stories.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    stories = data["stories"]
    title = stories[count-1]["title"]
    gender = stories[count-1]["main_character_gender"]
    num_parts = stories[count-1]["num_parts"]
    description = stories[count-1]["description"]
    tags = stories[count-1]["tags"]
    parts = stories[count-1]["parts"]

    return title, gender, num_parts, description, tags, parts

def generate_full_story(count, youtube):
    title, gender, num_parts, description, tags, parts = load_story(count)
    story_path = f"Stories/Story_{count}/Reddit_Story_Full.mp4"
    make_title_box(title)

    full_text = f""
    for part in parts: full_text += part["content"]

    generate_tts(title, full_text, gender)
    generate_video(story_path, cropped=False)
    if os.path.exists(story_path): cleanup()
    upload_video(youtube, story_path, title, description, tags)

def make_story():
    youtube = authenticate_youtube()
    print("Authenticated!")
    count = get_video_number()
    title, gender, num_parts, description, tags, parts = load_story(count)
    os.makedirs(f"Stories/Story_{count}", exist_ok=True)
    print("Story Retrieved")

    if num_parts == 1:
        title, gender, num_parts, description, tags, parts = load_story(count)
        story_path = f"Stories/Story_{count}/Reddit_Story_1.mp4"
        generate_tts(title, parts[0]["Content"], gender)
        make_title_box(title)
        generate_video(story_path)
        if os.path.exists(story_path): cleanup()
        upload_video(youtube, story_path, title, description, tags)
    else: 
        i = 3
        for part in parts:       
            title, gender, num_parts, description, tags, parts = load_story(count)
            story_path = f"Stories/Story_{count}/Reddit_Story_{i}.mp4"
            if num_parts == i:
                title = f"{title} (Final Part)"
                make_title_box(title)
                generate_tts(title, parts[i - 1]["content"], gender)
                generate_video(story_path)
                if os.path.exists(story_path): cleanup()
                upload_video(youtube, story_path, title, f"{description} (Final Part)", tags)
                break
            else:
                title = f"{title} (Part {i})"
                make_title_box(title)
                generate_tts(title, parts[i - 1]["content"], gender)
                generate_video(story_path)
                if os.path.exists(story_path): cleanup()
                upload_video(youtube, story_path, title, f"{description} (Part {i})", tags)
                i += 1

    generate_full_story(count, youtube)
    # TODO: REIMPLEMENT FULL STORY LOGIC + SAVING AUDIOS

    print("Stories Posted.")


if __name__ == "__main__":  
    make_story()