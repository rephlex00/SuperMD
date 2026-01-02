from abc import ABC, abstractmethod

from pydantic.dataclasses import dataclass
from sn2md.supernotelib import Notebook

TO_MARKDOWN_TEMPLATE = """###
Context (the last few lines of markdown from the previous page):
{context}
###
Convert the image to markdown:
- If there is a simple diagram that the mermaid syntax can achieve, create a mermaid codeblock of it.
- If most of the image is a drawing (not written text), add a #drawing tag and describe the drawing in no more than 8 words.
- When it is unclear what an image is, don't output anything for it.
- Use $$, $ latex math blocks for math equations.
- Support Obsidian syntaxes and dataview "field:: value" syntax.
- Do not wrap text in codeblocks.
"""

TO_TEXT_TEMPLATE = """
Convert the following image to text.
- If the image does not appear to be text, output a brief description (no more than 4 words), prepended with "Image: "
"""

DEFAULT_MD_TEMPLATE = """---
created: {{year_month_day}}
tags: supernote
---

{{llm_output}}

# Images
{% for image in images %}
- ![{{ image.name }}]({{ image.link }})
{%- endfor %}

{% if keywords %}
# Keywords
{% for keyword in keywords %}
- Page {{ keyword.page_number }}: {{ keyword.content }}
{%- endfor %}
{%- endif %}

{% if links %}
# Links
{% for link in links %}
- Page {{ link.page_number }}: {{ link.type }} {{ link.inout }} [[{{ link.name | replace('.note', '')}}]]
{%- endfor %}
{%- endif %}

{% if titles %}
# Titles
{% for title in titles %}
- Page {{ title.page_number }}: Level {{ title.level }} "{{ title.content }}"
{%- endfor %}
{%- endif %}
"""


@dataclass
class Config:
    # The path used to save the output files (images and output file). All template variables are available.
    output_path_template: str = "{{file_basename}}"
    # The name of the output files. All template variables are available.
    output_filename_template: str = "{{file_basename}}.md"
    # The prompt used to convert an image to markdown.
    prompt: str = TO_MARKDOWN_TEMPLATE
    # The prompt used to convert some image to plain text (used for header highlights (H1, H2, etc.))
    title_prompt: str = TO_TEXT_TEMPLATE
    # The jinja template used to output markdown files.
    template: str = DEFAULT_MD_TEMPLATE
    # The LLM model to use for conversion (e.g. gpt-4o-mini). Can be any model installed in the environment (https://llm.datasette.io/en/stable/plugins/index.html)
    model: str = "gpt-4o-mini"
    # The API KEY for the model selected.
    api_key: str | None = None

    # The API key, deprecated - use `api_key`
    openai_api_key: str | None = None

    def __post_init__(self):
        # support the deprecated configuration:
        if self.api_key is None:
            self.api_key = self.openai_api_key

@dataclass
class ConversionMetadata:
    # The input file name
    input_file: str
    # The hash of the input at the time of conversion
    input_hash: str
    # The file that was generated
    output_file: str
    # The hash of the output file at the time it was generated.
    output_hash: str

class ImageExtractor(ABC):
    @abstractmethod
    def extract_images(self, filename: str, output_path: str) -> list[str]:
        pass

    @abstractmethod
    def get_notebook(self, filename: str) -> Notebook | None:
        pass

