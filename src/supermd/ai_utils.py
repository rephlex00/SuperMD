from io import BytesIO
from PIL.Image import Image

import llm


class MissingAPIKeyError(Exception):
    """Raised when the configured LLM model requires an API key that isn't set."""

    def __init__(self, model_id: str, key_name: str, env_var: str | None):
        self.model_id = model_id
        self.key_name = key_name
        self.env_var = env_var
        lines = [
            f"No API key configured for model '{model_id}' (key: '{key_name}').",
        ]
        if env_var:
            lines.append(f"Set the {env_var} environment variable, or run:")
        else:
            lines.append("Run:")
        lines.append(f"  supermd config keys set {key_name}")
        super().__init__("\n".join(lines))


def validate_model_key(model: str) -> None:
    """Check that the given model has a usable API key.

    Raises MissingAPIKeyError if a key is required but not found.
    """
    llm_model = llm.get_model(model)
    if not llm_model.needs_key:
        return
    # get_key() checks env vars and the llm keystore
    if llm_model.get_key() is None:
        raise MissingAPIKeyError(
            model_id=model,
            key_name=llm_model.needs_key,
            env_var=getattr(llm_model, "key_env_var", None),
        )


def convert_image(text: str, attachment: llm.Attachment, model: str) -> str:
    llm_model = llm.get_model(model)
    response = llm_model.prompt(text, attachments=[attachment])
    return response.text()


def image_to_markdown(
    path: str,
    context: str,
    model: str,
    prompt: str,
    prompt_context: dict | None = None,
) -> str:
    variables = {"context": context}
    if prompt_context:
        variables.update(prompt_context)
    return convert_image(
        prompt.format(**variables), llm.Attachment(path=path), model
    )


def _image_to_bytes(image: Image) -> bytes:
    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()


def markdown_to_title(markdown: str, model: str, prompt: str) -> str:
    llm_model = llm.get_model(model)
    response = llm_model.prompt(prompt.format(markdown=markdown))
    return response.text().strip()


def image_to_text(image: Image, model: str, prompt: str) -> str:
    return convert_image(
        prompt, llm.Attachment(content=_image_to_bytes(image)), model
    )
