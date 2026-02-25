"""
Module: llm_client
Description: Initializes and manages the LLM client for the application

Usage:
    client = StructuredOllamaClient()
    response = client.generate(
        prompt="Generate a project proposal for building a web app",
        response_model=MyCustomSchema
    )
"""

from __future__ import annotations

import logging
from json import JSONDecodeError
from typing import Any, Type, TypeVar

import instructor
from instructor.exceptions import (
    IncompleteOutputException,
    InstructorRetryException,
    ValidationError as InstructorValidationError,
)
from openai import APITimeoutError, OpenAI
from pydantic import BaseModel, ValidationError

from app.settings import settings
from app.utils import dict2str


T = TypeVar("T", bound=BaseModel)
LLMCallPayload = dict[str, Any]

logger = logging.getLogger(__name__)


class StructuredOllamaClient:
    """An LLM Client that relies on the Ollama API, wrapped with Instructor for structured outputs."""

    def __init__(self, ollama_url: str = settings.ollama_url, log_level: str = settings.log_level):
        """An LLM Client that relies on the Ollama API, wrapped with Instructor for structured outputs.

        Args:
            ollama_url (str, optional): URL to the Ollama entrypoint. Defaults to settings.ollama_url.
            log_level (str, optional): Level for logging purposes. Defaults to settings.log_level.
        """
        openai_client = OpenAI(
            base_url=f"{ollama_url}/v1",
            api_key="ollama",  # required, but unused
        )
        # Wrap the client with Instructor to enable structured outputs
        self.client = instructor.from_openai(
            openai_client,
            mode=instructor.Mode.JSON,
        )
        logger.setLevel(log_level.upper())
        logger.debug("StructuredOllamaClient initialized.")

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_model: Type[T],
        model: str,
        max_retries: int = settings.instructor_max_retries,
        **kwargs,
    ) -> T:
        """Generates a structured response from the LLM using the chat endpoint.

        Args:
            prompt (str): User prompt with the payload.
            system_prompt (str): System prompt with the instructions.
            response_model (Type[T]): Expected response format.
            model (str, optional): Name of the LLM.
            max_retries (int, optional): Number of allowed retries. Defaults to settings.instructor_max_retries.

        Returns:
            T: LLM's response following the structure/format of Type[T]
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        return self._generate_with_smart_retries(model, messages, response_model, max_retries, **kwargs)

    def _generate_with_smart_retries(
        self, model: str, messages: list[dict[str, str]], response_model: Type[T], max_retries: int, **kwargs
    ) -> T:
        """Handle LLM retry calls when multiple attempts are necessary."""
        last_attempt_exception = None
        # For some reasons, the default value for max_retries in Instructor is 3. Here we ensure no retries,
        # at least none initiated by Instructor, as OpenAI API can also trigger retries for timeout errors, etc.
        payload = self._build_single_attempt_payload(model, messages, response_model, **kwargs)
        n_attempts = 0
        max_attempts = max_retries + 1
        while n_attempts < max_attempts:
            if n_attempts:
                payload = self._update_payload_for_retry(payload, last_attempt_exception)
            n_attempts += 1
            logger.debug("Trying attempt %s of %s.", n_attempts, max_attempts)
            try:
                return self._chat_completions_create(**payload)
            except InstructorRetryException as e:
                # Instructor has encapsulated all LLM calls into a retry mechanism. This means that instead of receiving
                # the precise exception, if any, we receive a generic InstructorRetryException, contradictory to what
                # their documentation says:
                # https://python.useinstructor.com/concepts/error_handling/#incompleteoutputexception
                last_attempt_exception = e.__cause__.last_attempt._exception
                if isinstance(last_attempt_exception, IncompleteOutputException):
                    logger.warning("SmartRetry: Output is incomplete due to a max_tokens length limit reached.")
                # A similar issue occurs with ValidationError retry mechanism, see:
                # https://github.com/567-labs/instructor/pull/1737 & https://github.com/567-labs/instructor/issues/1736
                elif isinstance(last_attempt_exception, (ValidationError, JSONDecodeError, InstructorValidationError)):
                    logger.warning("SmartRetry: Output is invalid and doesn't adhere to `response_model`'s schema.")
                # OpenAI API already has a retry mechanism for timeout, but not sure the timeout is gradually increased.
                elif isinstance(last_attempt_exception, APITimeoutError):
                    logger.warning("SmartRetry: Generation took too long, timeout reached.")
                else:
                    raise e
                if n_attempts >= max_attempts:
                    raise e

    def _chat_completions_create(self, **payload) -> T:
        """Call LLM with payload."""
        logger.debug(f"LLM request payload:\n{dict2str(payload)}")
        response = self.client.chat.completions.create(**payload)
        logger.debug(f"LLM reponse:\n{dict2str(response)}")
        return response

    @staticmethod
    def _update_payload_for_retry(payload: LLMCallPayload, e: Exception) -> LLMCallPayload:
        """Update the LLM call's payload for the next attempt based on the exception encounter during last attempt."""
        if isinstance(e, IncompleteOutputException):
            logger.debug("SmartRetry: Adding new instruction to request the model to be more concise.")
            new_instruction = "Be more concise."
            payload["messages"].append({"role": "system", "content": new_instruction})
            return payload
        if isinstance(e, (ValidationError, JSONDecodeError, InstructorValidationError)):
            logger.debug("SmartRetry: Feeding back the validation error to the model.")
            new_instruction = f"Adhere to the output's expected schema. Last attempt had the following error:\n{e!s}."
            payload["messages"].append({"role": "system", "content": new_instruction})
            return payload
        if isinstance(e, APITimeoutError):
            logger.debug("SmartRetry: Increasing timeout by 50%.")
            payload["timeout"] = payload.get("timeout", settings.httpx_timeout) * 1.5
            return payload
        return NotImplementedError(f"Cannot build new payload as {type(e)} is not yet supported.")

    @staticmethod
    def _build_single_attempt_payload(
        model: str, messages: list[dict[str, str]], response_model: Type[T], **kwargs
    ) -> LLMCallPayload:
        """Build a payload for an LLM call with `max_retries` set to 0."""
        payload = {
            "model": model,
            "messages": messages,
            "response_model": response_model,
        }
        payload.update(kwargs)
        payload["max_retries"] = 0  # Ensure no retries here, as by default Instructor sets it to 3
        return payload
