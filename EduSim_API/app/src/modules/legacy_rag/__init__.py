# Legacy chatbot-style RAG system
# Preserved for backup/reference only

from .vector_loader import vector_store
from .generator import generate_response
from .loader import load_all_pdfs

__all__ = ["vector_store", "generate_response", "load_all_pdfs"]
