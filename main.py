import os
import time
import uuid
from typing import List, Type, TypeVar

import replicate
import requests
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from lumaai import LumaAI
from openai import NOT_GIVEN, OpenAI
from pydantic import BaseModel


def get_temp_filename(extension: str) -> str:
    return f"./content/{uuid.uuid4()}.{extension}"


load_dotenv()

openai = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

elevenlabs = ElevenLabs(
    api_key=os.environ.get("ELEVENLABS_API_KEY"),
)

luma = LumaAI(
    auth_token=os.environ.get("LUMAAI_API_KEY"),
)


def generate_text(system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"} if json_mode else NOT_GIVEN,
    )
    if not response.choices[0].message.content:
        raise Exception("No response from OpenAI")
    return response.choices[0].message.content


T = TypeVar("T", bound=BaseModel)


def generate_json(system_prompt: str, user_prompt: str, model: Type[T]) -> T:
    data = generate_text(system_prompt, user_prompt, json_mode=True)
    return model.model_validate_json(data)


def generate_image(prompt: str) -> str:
    output = replicate.run("luma/photon", input={"prompt": prompt})

    filename = get_temp_filename("jpg")
    with open(filename, "wb") as file:
        file.write(output.read())

    return filename


def generate_video(prompt: str) -> str:
    generation = luma.generations.create(
        prompt=prompt,
    )

    completed = False
    while not completed:
        if not generation.id:
            raise RuntimeError("Generation ID is None")
        generation = luma.generations.get(id=generation.id)
        if generation.state == "completed":
            completed = True
        elif generation.state == "failed":
            raise RuntimeError(f"Generation failed: {generation.failure_reason}")
        print("Generating video..")
        time.sleep(3)

    if not generation.assets:
        raise RuntimeError("Generation has no video")

    video_url = generation.assets.video

    if not video_url:
        raise RuntimeError("Generation has no video URL")

    filename = get_temp_filename("mp4")
    response = requests.get(video_url, stream=True)
    with open(filename, "wb") as file:
        file.write(response.content)

    return filename


def generate_audio(text: str, voice: str = "Brian") -> str:
    audio = elevenlabs.generate(
        text=text,
        voice=voice,
        model="eleven_multilingual_v2",
    )
    filename = get_temp_filename("mp3")
    with open(filename, "wb") as file:
        for chunk in audio:
            file.write(chunk)
    return filename


language = "German"

idea = generate_text(
    system_prompt="If you are a screenwriter for the TV show Beyond All Belief, or in German X-Faktor das Unfassbare, generate an idea for a short story for that particular TV show. Don't write acts, scenes or anything else. Just a quick idea. Include a twist.",
    user_prompt=f"Return the idea as short text in {language}.",
)


class Character(BaseModel):
    id: str
    name: str
    description: str
    appearance: str


class Characters(BaseModel):
    characters: List[Character]


characters = generate_json(
    system_prompt="Generate the characters for the short story.",
    user_prompt="""Return the characters as a JSON:
    {
        "characters": [
            {
                "id": a unique identifier for the character as a string, e.g the name in lower case (must be unique)
                "name": the name of the character
                "description": a short description of the character
                "appearance": a short description of the character's appearance in style of prompt for an image generator, add country of origin, age, gender, hair color, eye color, ethnicity, clothing, etc.
            }
        ]
    }
    in {language}.""",
    model=Characters,
)

print(characters)


class Act(BaseModel):
    description: str
    characters: List[Character]
