# ADDED [PROMPT #36]: base and tone rules appear exactly once in each assembled prompt.
import pytest

from trip_journal.agent.journal import JournalAgent
from trip_journal.agent.llm import FakeLLMClient
from trip_journal.agent.prompts import PromptLibrary
from trip_journal.agent.tools import default_registry
from trip_journal.domain.journal_merge import Tone


@pytest.mark.parametrize("tone", ["concise", "detailed", "casual"])
def test_prompt_composition(tone: Tone) -> None:
    lib = PromptLibrary()
    agent = JournalAgent(FakeLLMClient([]), default_registry(), lib)
    prompt = agent.prompt(tone)
    assert "Every sentence that states a fact" in prompt
    assert "Write exactly one section per listed slot" in prompt
    assert prompt == lib.get("journal") + "\n\n" + lib.get(f"journal_tone_{tone}", shared=False)
    assert agent.prompt(tone, True) == prompt + "\n\n" + lib.get("journal_summary", shared=False)
