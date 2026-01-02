from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

import os

class JobFlags(BaseModel):
    model: str = Field(default_factory=lambda: os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    level: str = "INFO"
    force: bool = False
    progress: bool = True

class JobConfig(BaseModel):
    name: str = "unnamed"
    input: str
    output: str
    config: Optional[str] = None
    env_file: Optional[str] = None
    extra_args: List[str] = Field(default_factory=list)
    flags: JobFlags = Field(default_factory=JobFlags)

    @staticmethod
    def _expand(v: Any) -> Any:
        if isinstance(v, str):
            return os.path.expandvars(v)
        return v

    def __init__(self, **data):
        # Expand vars in creating
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = os.path.expandvars(v)
        super().__init__(**data)

class BatchConfig(BaseModel):
    defaults: Dict[str, Any] = Field(default_factory=dict)
    jobs: List[Dict[str, Any]] = Field(default_factory=list)

def load_jobs_config(path: str | Path) -> BatchConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    # Pre-expand defaults in the dictionary before creating model if possible, 
    # but BatchConfig stores them as Dict, so we can iterate.
    if "defaults" in data:
        for k, v in data["defaults"].items():
            if isinstance(v, str):
                data["defaults"][k] = os.path.expandvars(v)
                
    return BatchConfig(**data)

def merge_defaults(job_data: Dict[str, Any], defaults: Dict[str, Any]) -> JobConfig:
    # Start with a copy of defaults
    merged = defaults.copy()
    
    # 1. Handle Deep Merge for 'flags'
    # If both have flags, we update the default flags with job flags
    if "flags" in defaults and "flags" in job_data:
        merged_flags = defaults["flags"].copy()
        merged_flags.update(job_data["flags"])
        merged["flags"] = merged_flags
    elif "flags" in job_data:
        # Defaults had no flags, but job does
        merged["flags"] = job_data["flags"]
    
    # 2. Handle List Concatenation for 'extra_args'
    defaults_args = defaults.get("extra_args", [])
    job_args = job_data.get("extra_args", [])
    merged["extra_args"] = defaults_args + job_args
    
    # 3. Update all other scalar fields from job_data
    for k, v in job_data.items():
        if k not in ("flags", "extra_args"):
            merged[k] = v
            
    # Ensure flags dict exists for Pydantic validation
    if "flags" not in merged:
        merged["flags"] = {}
        
    return JobConfig(**merged)
