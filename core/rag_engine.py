import os
import chromadb
from chromadb.utils import embedding_functions
# Note: sentence-transformers is used implicitly by default embedding function if not specified, 
# but explicitly importing it ensures we can control it if needed.
# For simplicity, we'll use the default all-MiniLM-L6-v2 which Chroma uses by default.

class RAGEngine:
    def __init__(self, project_path):
        self.project_path = project_path
        self.db_path = os.path.join(project_path, ".inkwell_rag")
        
        # Initialize Client
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # Create or get collection
        # We use the default embedding function (all-MiniLM-L6-v2)
        self.collection = self.client.get_or_create_collection(name="project_docs")

    def index_file(self, file_path, content):
        """Indexes a single file. Splits content into chunks."""
        if not content:
            return

        # Simple chunking by paragraphs for now
        chunks = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        if not chunks:
            return

        # Generate IDs based on file path and index
        ids = [f"{file_path}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": file_path} for _ in chunks]

        # Upsert (overwrite if exists)
        self.collection.upsert(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Indexed {len(chunks)} chunks for {file_path}")

    def query(self, query_text, n_results=3):
        """Retrieves relevant chunks for the query."""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        # results['documents'] is a list of lists (one list per query)
        if results['documents']:
            return results['documents'][0]
        return []

    def index_project(self):
        """Walks the project and indexes all markdown files."""
        for root, dirs, files in os.walk(self.project_path):
            if ".inkwell_rag" in root:
                continue
            for file in files:
                if file.endswith((".md", ".txt")):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self.index_file(path, content)
                    except Exception as e:
                        print(f"Error indexing {path}: {e}")
