# Application Architecture

This document maps the `sn2md` application structure and data flow using Mermaid diagrams.

## Module Dependency Graph

This diagram shows how the internal modules interact with each other.

```mermaid
graph TD
    %% Entry Points
    CLI[sn2md.cli] --> Batches[sn2md.batches]
    CLI --> Watcher[sn2md.watcher]
    CLI --> Report[sn2md.report]
    
    %% Core Logic
    Batches --> Converter[sn2md.converter]
    Watcher --> Batches
    
    %% Data Processing
    Converter --> Context[sn2md.context]
    Converter --> Extractors{Extractors}
    Converter --> AI[sn2md.ai_utils]
    Converter --> Metadata[sn2md.metadata_db]
    
    %% Extractors
    subgraph Extractors
        NoteExt[Note Extractor]
        PDFExt[PDF Extractor]
        PNGExt[PNG Extractor]
        AtelierExt[Atelier Extractor]
    end
    
    %% Supporting Modules
    Context --> SupernoteLib[sn2md.supernotelib]
    Report --> Metadata
    Batches --> JobConfig[sn2md.job_config]
    CLI --> JobConfig
    
    %% External
    AI --> LLM((LLM Provider))
    Converter --> Template((Jinja2))
```

## Conversion Flow (Sequence)

This diagram illustrates the process of converting a single file.

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Converter
    participant Extractor
    participant Context
    participant AI
    participant Metadata

    User->>CLI: sn2md file input.note
    CLI->>Converter: convert_file(input.note)
    
    Converter->>Metadata: verify_metadata_file()
    alt File Unchanged / Output Modified
        Metadata-->>Converter: Raise Skip Exception
        Converter-->>CLI: Log Skip
    end
    
    Converter->>Extractor: extract_images()
    Extractor-->>Converter: [images]
    
    loop For Each Page
        Converter->>AI: image_to_markdown(image)
        AI-->>Converter: markdown_text
    end
    
    Converter->>Extractor: get_notebook()
    Extractor-->>Converter: Notebook Object
    
    Converter->>Context: create_context(notebook, images, text)
    Context-->>Converter: Context Dict
    
    Converter->>Converter: Render Template & Write Output
    
    Converter->>Metadata: upsert_entry(hashes, paths)
    Converter-->>CLI: Success
```

## Directory Structure

```mermaid
graph LR
    Root[src/sn2md] --> CLIB[cli.py]
    Root --> Batch[batches.py]
    Root --> Watch[watcher.py]
    Root --> Conv[converter.py]
    Root --> Ctx[context.py]
    Root --> Rep[report.py]
    Root --> Importers[importers/]
    
    Importers --> Note[note.py]
    Importers --> PDF[pdf.py]
    Importers --> PNG[png.py]
    Importers --> Atelier[atelier.py]
```
