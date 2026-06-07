/** Default prompt, title prompt, and output template — ported from supermd/config.py. */

export const DEFAULT_PROMPT = `###
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
`;

export const DEFAULT_TITLE_PROMPT = `Convert the following image to text.
- If the image does not appear to be text, output a brief description (no more than 4 words), prepended with "Image: "
`;

export const DEFAULT_NOTE_TITLE_PROMPT = '';

/**
 * Default output template. `noteEmbed` holds an image-style wikilink to the
 * original .note (embed mode); `images` holds extracted PNG links (extract-png
 * mode). Only one is populated per conversion.
 */
export const DEFAULT_TEMPLATE = `---
created: {{DATE:YYYY-MM-DD}}
tags: supernote
---

{{ llm_output }}
{% if noteEmbed %}

{{ noteEmbed }}
{%- endif %}
{% if images %}

# Images
{% for image in images %}
- ![{{ image.name }}]({{ image.link }})
{%- endfor %}
{%- endif %}
{% if keywords %}

# Keywords
{% for keyword in keywords %}
- Page {{ keyword.page_number }}: {{ keyword.content }}
{%- endfor %}
{%- endif %}
{% if links %}

# Links
{% for link in links %}
- Page {{ link.page_number }}: {{ link.type }} {{ link.inout }} [[{{ link.name | replace('.note', '') }}]]
{%- endfor %}
{%- endif %}
`;

export const DEFAULT_OUTPUT_PATH_TEMPLATE = '{{file_basename}}';
export const DEFAULT_OUTPUT_FILENAME_TEMPLATE = '{{file_basename}}.md';
