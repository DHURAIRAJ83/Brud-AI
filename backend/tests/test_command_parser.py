import pytest
from ai.command_parser import command_parser

@pytest.mark.asyncio
async def test_parse_open_app():
    # Tamil
    action = await command_parser.parse("VS Code திற")
    assert action.tool == "desktop.open_app"
    assert action.params["app"] == "vscode"
    
    # English
    action = await command_parser.parse("open chrome")
    assert action.tool == "desktop.open_app"
    assert action.params["app"] == "chrome"

@pytest.mark.asyncio
async def test_parse_close_app():
    action = await command_parser.parse("Chrome மூடு")
    assert action.tool == "desktop.close_app"
    assert action.params["app"] == "chrome"

@pytest.mark.asyncio
async def test_parse_list_files():
    action = await command_parser.parse("Downloads folder files காட்டு")
    assert action.tool == "files.list"
    assert action.params["path"] == "downloads"

@pytest.mark.asyncio
async def test_parse_create_folder():
    action = await command_parser.parse("Projects folder உருவாக்கு")
    assert action.tool == "files.create_folder"
    assert action.params["name"] == "Projects"
