"""Production entrypoint: serve the Gradio app with uvicorn on 0.0.0.0:$PORT.

Used by render.yaml. Mounting via FastAPI avoids Blocks.launch()'s localhost
reachability check, which fails inside some hosting sandboxes.
"""
import os

import gradio as gr
import uvicorn
from fastapi import FastAPI

import app as battleship

server = FastAPI()
gr.mount_gradio_app(
    server,
    battleship.app,
    path="/",
    css=battleship.ARCADE_CSS + battleship.WORD_MODE_CSS,
    head=f"<script>{battleship.GAME_JS}</script>",
)

if __name__ == "__main__":
    uvicorn.run(server, host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
