
import torch
from sentence_transformers import SentenceTransformer

from ..utils.errors import EmbeddingError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Embedder:
    def __init__(
        self,
        model_name: str = "jinaai/jina-embeddings-v2-base-code",
        device: str | None = None,
    ):
        self.model_name = model_name
        self.device = device or self._select_device()
        self._model: SentenceTransformer | None = None

    def _select_device(self) -> str:
        if torch.cuda.is_available():
            device = "cuda"
            logger.info("CUDA available, using GPU for embeddings")
        elif torch.backends.mps.is_available():
            device = "mps"
            logger.info("MPS available, using Apple Silicon GPU for embeddings")
        else:
            device = "cpu"
            logger.info("Using CPU for embeddings")
        return device

    def load_model(self) -> None:
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(
                self.model_name, device=self.device, trust_remote_code=True
            )
            logger.info(f"Model loaded successfully on {self.device}")
        except Exception as e:
            raise EmbeddingError(
                f"Failed to load model: {str(e)}",
                {"model_name": self.model_name, "device": self.device},
            ) from e

    def encode(
        self, texts: list[str], batch_size: int = 32, show_progress: bool = False
    ) -> list[list[float]]:
        if not self._model:
            raise EmbeddingError("Model not loaded. Call load_model() first.")

        try:
            embeddings = self._model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            )

            logger.info(f"Encoded {len(texts)} texts into embeddings")
            return embeddings.tolist()
        except Exception as e:
            raise EmbeddingError(
                f"Failed to encode texts: {str(e)}",
                {"text_count": len(texts), "batch_size": batch_size},
            ) from e

    def encode_single(self, text: str) -> list[float]:
        return self.encode([text], batch_size=1)[0]

    def get_dimension(self) -> int | None:
        if not self._model:
            raise EmbeddingError("Model not loaded. Call load_model() first.")
        return self._model.get_sentence_embedding_dimension()
