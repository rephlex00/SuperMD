# Test fixtures

This directory holds binary inputs that are too awkward to generate
on-the-fly. Place files here and the test suite picks them up automatically.

## `sample.note`

A tiny Supernote `.note` file used for end-to-end conversion tests against
the real `supernotelib` parser.

**To enable these tests:**

1. Take any short note on a Supernote device (1-2 pages is ideal).
2. Export the `.note` file (e.g. via Supernote Cloud, Files app on the
   device, or USB).
3. Drop it here as `sample.note` (literal filename).
4. Run `pytest sidecar/tests/test_engine_pipeline.py`.

The tests that depend on this fixture call `pytest.skip(...)` cleanly when
the file is missing, so CI keeps passing on a fresh checkout. They light up
as soon as you commit the file.

**Privacy note:** anything in a committed `.note` ships with the repo. Use
a throwaway note or strip the content with the Supernote app first.

## `sample.spd`

Same idea, but for Supernote Atelier (`.spd`) format. Optional — useful for
covering the atelier importer path.

## `obsidian.json`

Generated on the fly by the `fake_obsidian_registry` fixture in
`conftest.py` — nothing to commit here.
