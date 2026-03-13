from io import BytesIO
from PIL.Image import Image

import llm

def convert_image(
    text: str, attachment: llm.Attachment, api_key: str | None, model: str
) -> str:
    # TODO handle no such model
    llm_model = llm.get_model(model)
    if api_key:
        llm_model.key = api_key
    response = llm_model.prompt(text, attachments=[attachment])
    return response.text()


def image_to_markdown(
    path: str,
    context: str,
    api_key: str | None,
    model: str,
    prompt: str,
    prompt_context: dict | None = None,
) -> str:
    variables = {"context": context}
    if prompt_context:
        variables.update(prompt_context)
    return convert_image(
        prompt.format(**variables), llm.Attachment(path=path), api_key, model
    )


def _image_to_bytes(image: Image) -> bytes:
    # Convert PIL Image to bytes
    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()


def markdown_to_title(markdown: str, api_key: str | None, model: str, prompt: str) -> str:
    llm_model = llm.get_model(model)
    if api_key:
        llm_model.key = api_key
    response = llm_model.prompt(prompt.format(markdown=markdown))
    return response.text().strip()


def image_to_text(image: Image, api_key: str | None, model: str, prompt: str) -> str:
    return convert_image(
        prompt, llm.Attachment(content=_image_to_bytes(image)), api_key, model
    )
