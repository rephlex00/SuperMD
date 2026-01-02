import os
from datetime import datetime
from sn2md.importer import create_basic_context
from sn2md.ai_utils import image_to_markdown
# Mock setup
file_name = "test.note"
with open(file_name, "w") as f:
    f.write("dummy")

basic_context = create_basic_context("test", file_name)
print(f"Basic Context Keys: {list(basic_context.keys())}")

prompt = """
###
Context (the last few lines of markdown from the previous page):
{context}
###
Convert the image to markdown:
- If there has a simple diagram...
- ...
- For incomplete checklist items (empty boxes), append ' ➕ {year_month_day}' immediately after the item text...
"""

try:
    variables = {"context": "PREVIOUS_CONTEXT"}
    variables.update(basic_context)
    formatted = prompt.format(**variables)
    print("Formatting successful")
except Exception as e:
    print(f"Formatting failed: {e}")
