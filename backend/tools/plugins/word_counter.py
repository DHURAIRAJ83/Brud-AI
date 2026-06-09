"""
Example Plugin — Word Counter
------------------------------
Demonstrates the plugin contract.

To create your own plugin:
1. Copy this file into tools/plugins/
2. Set PLUGIN_NAME, PLUGIN_INTENTS, PLUGIN_DESCRIPTION
3. Implement: async def execute(message: str, **kwargs) -> str
4. Restart the backend — it auto-loads!
"""

PLUGIN_NAME = "word_counter"
PLUGIN_INTENTS = ["count_words", "word_count"]
PLUGIN_DESCRIPTION = "Counts words, sentences, and characters in a given text."


async def execute(message: str, **kwargs) -> str:
    # Strip common command prefixes
    for prefix in ["count words", "word count", "count"]:
        if message.lower().startswith(prefix):
            message = message[len(prefix):].lstrip(": ").strip()

    if not message:
        return "Please provide some text to count."

    words = len(message.split())
    sentences = message.count(".") + message.count("!") + message.count("?")
    chars = len(message)
    chars_no_space = len(message.replace(" ", ""))

    return (
        f"📊 **Text Statistics:**\n"
        f"- Words: **{words}**\n"
        f"- Sentences: **{sentences}**\n"
        f"- Characters (with spaces): **{chars}**\n"
        f"- Characters (no spaces): **{chars_no_space}**"
    )
