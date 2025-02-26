import logging
import secrets
from typing import TypeVar, Optional, List, Dict

from fidesops.schemas.masking.masking_secrets import (
    MaskingSecretMeta,
    MaskingSecretCache,
    SecretType,
)
from fidesops.util.cache import get_masking_secret_cache_key, get_cache

T = TypeVar("T")
logger = logging.getLogger(__name__)


class SecretsUtil:
    @staticmethod
    def get_or_generate_secret(
        privacy_request_id: Optional[str],
        secret_type: SecretType,
        masking_secret_meta: MaskingSecretMeta[T],
    ) -> T:
        if privacy_request_id is not None:
            secret: T = SecretsUtil._get_secret_from_cache(
                privacy_request_id, secret_type, masking_secret_meta
            )
            if not secret:
                logger.warning(
                    f"Secret type {secret_type} expected from cache but was not present for masking strategy {masking_secret_meta.masking_strategy}"
                )
            return secret
        else:
            # expected for standalone masking service
            return masking_secret_meta.generate_secret_func(
                masking_secret_meta.secret_length
            )

    @staticmethod
    def _get_secret_from_cache(
        privacy_request_id: str,
        secret_type: SecretType,
        masking_secret_meta: MaskingSecretMeta[T],
    ) -> T:
        cache = get_cache()
        masking_secret_cache_key: str = get_masking_secret_cache_key(
            privacy_request_id=privacy_request_id,
            masking_strategy=masking_secret_meta.masking_strategy,
            secret_type=secret_type,
        )
        return cache.get_encoded_by_key(masking_secret_cache_key)

    @staticmethod
    def generate_secret_string(length: int) -> str:
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_secret_bytes(length: int) -> bytes:
        return secrets.token_bytes(length)

    @staticmethod
    def build_masking_secrets_for_cache(
        masking_secret_meta: Dict[SecretType, MaskingSecretMeta[T]],
    ) -> List[MaskingSecretCache[T]]:
        masking_secrets = []
        for secret_type in masking_secret_meta.keys():
            meta = masking_secret_meta[secret_type]
            secret: T = meta.generate_secret_func(meta.secret_length)
            masking_secrets.append(
                MaskingSecretCache[T](
                    secret=secret,
                    masking_strategy=meta.masking_strategy,
                    secret_type=secret_type,
                )
            )
        return masking_secrets
