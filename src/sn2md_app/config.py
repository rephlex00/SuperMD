from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

class JobFlags(BaseModel):
    model: str = "gpt-4o-mini"
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

class BatchConfig(BaseModel):
    defaults: Dict[str, Any] = Field(default_factory=dict)
    jobs: List[Dict[str, Any]] = Field(default_factory=list)

def load_jobs_config(path: str | Path) -> BatchConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return BatchConfig(**data)

def merge_defaults(job_data: Dict[str, Any], defaults: Dict[str, Any]) -> JobConfig:
    # Merge logic similar to sn2md-batches.sh (job overrides defaults)
    merged = defaults.copy()
    
    # Deep merge flags if present
    if "flags" in defaults and "flags" in job_data:
        merged_flags = defaults["flags"].copy()
        merged_flags.update(job_data["flags"])
        merged["flags"] = merged_flags
    
    # Merge extra args (append)
    if "extra_args" in defaults:
        merged["extra_args"] = defaults["extra_args"] + job_data.get("extra_args", [])
        
    merged.update(job_data)
    
    # Ensure flags dict exists for Pydantic validation
    if "flags" not in merged:
        merged["flags"] = {}
        
    return JobConfig(**merged)
