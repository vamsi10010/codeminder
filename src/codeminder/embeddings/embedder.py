import time
from contextlib import contextmanager
from typing import Any

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

    def _clear_gpu_cache(self) -> None:
        """Clear GPU cache to free memory after embedding operations.

        This is critical to prevent CUDA OOM errors during long indexing sessions.
        Should be called after each batch of embeddings is generated.
        """
        if self.device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug("Cleared CUDA cache")
        elif self.device == "mps" and torch.backends.mps.is_available():
            if hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()
                logger.debug("Cleared MPS cache")

    @contextmanager
    def _inference_mode(self) -> Any:
        """Context manager for inference with automatic GPU cleanup.

        Uses torch.inference_mode() for better performance and memory efficiency
        compared to torch.no_grad(). Automatically clears GPU cache on exit.
        """
        with torch.inference_mode():
            try:
                yield
            finally:
                self._clear_gpu_cache()

    def load_model(self, token_limit: int | None = None) -> None:
        """Load the embedding model and optionally validate token limit.

        Args:
            token_limit: Optional token limit to validate against model's max_seq_length.
                        If provided, will raise error if limit exceeds model capacity.

        Raises:
            EmbeddingError: If model fails to load or token limit is invalid.
        """
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(
                self.model_name, device=self.device, trust_remote_code=True
            )

            # Validate token limit if provided
            if token_limit is not None:
                max_length = self._model.get_max_seq_length()
                if max_length and token_limit > max_length:
                    raise ValueError(
                        f"Token limit {token_limit} exceeds model's maximum sequence "
                        f"length of {max_length}"
                    )

            logger.info(f"Model loaded successfully on {self.device}")
        except Exception as e:
            raise EmbeddingError(
                f"Failed to load model: {str(e)}",
                {"model_name": self.model_name, "device": self.device},
            ) from e

    def encode(
        self,
        texts: list[str],
        batch_size: int = 4,
        show_progress: bool = False,
        max_retries: int = 3,
    ) -> list[list[float]]:
        if not self._model:
            raise EmbeddingError("Model not loaded. Call load_model() first.")

        last_error = None
        for attempt in range(max_retries):
            try:
                # Use inference mode context for efficient GPU memory management
                with self._inference_mode():
                    embeddings = self._model.encode(
                        texts,
                        batch_size=batch_size,
                        show_progress_bar=show_progress,
                        convert_to_numpy=True,
                    )

                logger.info(f"Encoded {len(texts)} texts into embeddings")
                result: list[list[float]] = embeddings.tolist()
                return result
            except Exception as e:
                last_error = e
                # Clear cache on error to recover memory
                self._clear_gpu_cache()
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Encoding attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} encoding attempts failed")

        raise EmbeddingError(
            f"Failed to encode texts after {max_retries} attempts: {str(last_error)}",
            {"text_count": len(texts), "batch_size": batch_size},
        ) from last_error

    def encode_single(self, text: str) -> list[float]:
        return self.encode([text], batch_size=1)[0]

    def encode_chunks(
        self, chunks: list[dict[str, Any]], show_progress: bool = False
    ) -> list[list[float]]:
        """Encode code chunks with automatic GPU memory cleanup.

        Args:
            chunks: List of chunk dictionaries with 'source_code' field
            show_progress: Whether to show progress bar

        Returns:
            List of embedding vectors
        """
        texts = [chunk["source_code"] for chunk in chunks]
        embeddings = self.encode(texts, show_progress=show_progress)
        # Explicit cache clear after chunk encoding to prevent memory buildup
        self._clear_gpu_cache()
        return embeddings

    def get_dimension(self) -> int | None:
        if not self._model:
            raise EmbeddingError("Model not loaded. Call load_model() first.")
        return self._model.get_sentence_embedding_dimension()

    def cleanup(self) -> None:
        """Clean up GPU resources and clear cache.

        Should be called when the embedder is no longer needed or during
        graceful shutdown to free GPU memory.
        """
        self._clear_gpu_cache()
        logger.info("Embedder GPU resources cleaned up")
