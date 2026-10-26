"""The linker moved to ai/james_ai/linker.py (Tasnim owns it).
This forwarder keeps store.py working without editing it; Ivan can drop it
once store.py imports from ai.james_ai.linker directly."""
from ai.james_ai.linker import Sample, link  # noqa: F401
