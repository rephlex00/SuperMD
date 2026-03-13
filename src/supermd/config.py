import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


# Default prompts — used when no config file is loaded

DEFAULT_PROMPT = """\
###
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

DEFAULT_TITLE_PROMPT = """\
Convert the following image to text.
- If the image does not appear to be text, output a brief description (no more than 4 words), prepended with "Image: "
"""

DEFAULT_TEMPLATE = """\
---
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


class ProcessingDefaults(BaseModel):
    force: bool = False
    progress: bool = True
    level: str = "INFO"
    cooldown: float = 5.0


class JobDefinition(BaseModel):
    name: str = "unnamed"
    input: str
    output: str
    # Per-job overrides — None means inherit from top-level config
    model: str | None = None
    force: bool | None = None
    progress: bool | None = None
    level: str | None = None
    cooldown: float | None = None


class SuperMDConfig(BaseModel):
    """Unified configuration for SuperMD."""

    # AI settings
    model: str = "gpt-4o-mini"

    # Prompts
    prompt: str = DEFAULT_PROMPT
    title_prompt: str = DEFAULT_TITLE_PROMPT
    note_title_prompt: str | None = None

    # Output templates
    template: str = DEFAULT_TEMPLATE
    output_path_template: str = "{{file_basename}}"
    output_filename_template: str = "{{file_basename}}.md"

    # Processing defaults
    defaults: ProcessingDefaults = Field(default_factory=ProcessingDefaults)

    # Job definitions (used by `supermd run` and `supermd watch`)
    jobs: list[JobDefinition] = Field(default_factory=list)

    def resolve_job(self, job: JobDefinition) -> dict:
        """Resolve a job definition by merging with top-level config defaults.

        Returns a dict with resolved values for model, force, progress, level, cooldown,
        plus expanded input/output paths.
        """
        return {
            "model": job.model or self.model,
            "force": job.force if job.force is not None else self.defaults.force,
            "progress": job.progress if job.progress is not None else self.defaults.progress,
            "level": job.level or self.defaults.level,
            "cooldown": job.cooldown if job.cooldown is not None else self.defaults.cooldown,
            "input": os.path.expanduser(os.path.expandvars(job.input)),
            "output": os.path.expanduser(os.path.expandvars(job.output)),
            "name": job.name,
        }


def _expand_strings(data):
    """Recursively expand environment variables in string values."""
    if isinstance(data, dict):
        return {k: _expand_strings(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_expand_strings(item) for item in data]
    if isinstance(data, str):
        return os.path.expandvars(data)
    return data


def load_config(path: str | Path) -> SuperMDConfig:
    """Load a unified SuperMD YAML config file."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    data = _expand_strings(data)
    return SuperMDConfig(**data)
