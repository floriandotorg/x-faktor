import os
import uuid

import replicate
from dotenv import load_dotenv
from openai import OpenAI


def get_temp_filename(extension: str) -> str:
    return f"./content/{uuid.uuid4()}.{extension}"


load_dotenv()

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)


def generate_text(system_prompt: str, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    if not response.choices[0].message.content:
        raise Exception("No response from OpenAI")
    return response.choices[0].message.content


def generate_image(prompt: str) -> str:
    output = replicate.run("luma/photon", input={"prompt": prompt})

    filename = get_temp_filename("jpg")
    with open(filename, "wb") as file:
        file.write(output.read())

    return filename


print(generate_image("chrome sports car by the sea"))
