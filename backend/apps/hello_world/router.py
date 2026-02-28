"""Hello World app router — a single greeting endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/greet")
async def greet(name: str = "World"):
    """Return a greeting message."""
    return {"message": f"Hello, {name}!", "app": "hello-world"}


@router.get("/info")
async def info():
    """Return app info."""
    return {
        "name": "Hello World",
        "version": "0.1.0",
        "description": "A minimal example app for the PromptForge platform.",
    }
