from typing import Any, List, Optional

from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.memory.types import (
    BaseComposableMemory,
    BaseMemory,
)
from llama_index.core.memory import ChatMemoryBuffer

DEFAULT_INTRO_HISTORY_MESSAGE = "Below are a set of relevant dialogues retrieved from potentially several memory sources:"
DEFAULT_OUTRO_HISTORY_MESSAGE = "This is the end of the of retrieved message dialogues."


class SimpleComposableMemory(BaseComposableMemory):
    """A simple composition of potentially several memory sources.

    This composable memory considers one of the memory sources as the main
    one and the others as secondary. The secondary memory sources get added to
    the chat history only in either the system prompt or to the first user
    message within the chat history.
    """

    _primary_memory: BaseMemory = PrivateAttr()
    _secondary_memory_sources: List[BaseMemory] = PrivateAttr()

    def __init__(self, sources: List[BaseMemory]) -> None:
        if len(sources) == 0:
            raise ValueError("Must supply at least one memory source.")

        self._primary_memory = sources[0]
        self._secondary_memory_sources = sources[1:]
        super().__init__(sources=sources)

    @classmethod
    def class_name(cls) -> str:
        """Class name."""
        return "SimpleComposableMemory"

    @property
    def primary_memory(self) -> BaseMemory:
        """The primary memory getter."""
        return self._primary_memory

    @property
    def secondary_memory_sources(self) -> List[BaseMemory]:
        """Getter for secondary memory sources."""
        return self._secondary_memory_sources

    @classmethod
    def from_defaults(
        cls,
        sources: Optional[List[BaseMemory]] = None,
    ) -> "SimpleComposableMemory":
        """Create a simple composable memory from an LLM."""
        sources = sources or [ChatMemoryBuffer.from_defaults()]

        return cls(sources=sources)

    def _format_secondary_messages(
        self, secondary_chat_histories: List[List[ChatMessage]]
    ) -> str:
        """Formats retrieved historical messages into a single string."""
        # TODO: use PromptTemplate for this
        formatted_history = "\n\n" + DEFAULT_INTRO_HISTORY_MESSAGE + "\n"
        for ix, chat_history in enumerate(secondary_chat_histories):
            formatted_history += (
                f"\n=====Relevant messages from memory source {ix + 1}=====\n\n"
            )
            for m in chat_history:
                formatted_history += f"\t{m.role.upper()}: {m.content}\n"
            formatted_history += (
                f"\n=====End of relevant messages from memory source {ix + 1}======\n\n"
            )

        formatted_history += DEFAULT_OUTRO_HISTORY_MESSAGE
        return formatted_history

    def get(self, input: Optional[str] = None, **kwargs: Any) -> List[ChatMessage]:
        """Get chat history."""
        return self._compose_message_histories(input, **kwargs)

    def _compose_message_histories(
        self, input: Optional[str] = None, **kwargs: Any
    ) -> List[ChatMessage]:
        """Get chat history."""
        # get from primary
        messages = self._primary_memory.get(input=input, **kwargs)

        # get from secondary
        secondary_histories = []
        for mem in self._secondary_memory_sources:
            secondary_history = mem.get(input, **kwargs)
            if len(secondary_history) > 0:
                secondary_histories.append(secondary_history)

        # format secondary memory
        if len(secondary_histories) > 0:
            single_secondary_memory_str = self._format_secondary_messages(
                secondary_histories
            )

            # add single_secondary_memory_str to chat_history
            if len(messages) > 0 and messages[0].role == MessageRole.SYSTEM:
                system_message = messages[0].content.split(
                    DEFAULT_INTRO_HISTORY_MESSAGE
                )[0]
                messages[0] = ChatMessage(
                    content=system_message.strip() + single_secondary_memory_str,
                    role=MessageRole.SYSTEM,
                )
            else:
                messages.insert(
                    0,
                    ChatMessage(
                        content="You are a helpful assistant."
                        + single_secondary_memory_str,
                        role=MessageRole.SYSTEM,
                    ),
                )
        return messages

    def get_all(self) -> List[ChatMessage]:
        """Get all chat history.

        Uses primary memory get_all only.
        """
        return self._primary_memory.get_all()

    def put(self, message: ChatMessage) -> None:
        """Put chat history."""
        self._primary_memory.put(message)
        for mem in self._secondary_memory_sources:
            mem.put(message)

    def set(self, messages: List[ChatMessage]) -> None:
        """Set chat history."""
        self._primary_memory.set(messages)
        for mem in self._secondary_memory_sources:
            mem.set(messages)

    def reset(self) -> None:
        """Reset chat history."""
        self._primary_memory.reset()

    def reset_all(self) -> None:
        """Reset all chat histories."""
        self._primary_memory.reset()
        for mem in self._secondary_memory_sources:
            mem.reset()
