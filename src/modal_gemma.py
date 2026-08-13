"""Target 2: Gemma-2-9B-IT on Modal via SGLang, OpenAI-compatible, logprobs on.

    modal deploy src/modal_gemma.py

prints a URL like https://<workspace>--gemma-sglang-serve.modal.run — put it in .env
as MODAL_BASE_URL with `/v1` appended, and `GemmaModalClient` talks to it like any
OpenAI endpoint.

Needs a Modal secret named "huggingface" holding HF_TOKEN:
    modal secret create huggingface HF_TOKEN=hf_...

google/gemma-2-9b-it is a GATED repo: accept the licence on the model page with the
same HF account the token belongs to, or the download 401s.

Cost control: `scaledown_window` idles the container down quickly and
`max_containers=1` keeps the run inside the ~$30 Modal budget. Nothing here is run by
the scaffolding — deploy it by hand when you're ready to collect Gemma episodes.
"""

import modal

MODEL_NAME = "google/gemma-2-9b-it"
MODEL_REVISION = "main"  # pin to a commit sha before data collection
PORT = 8000

# 9B in bf16 is ~18.5 GB of weights. An A10G (24 GB) leaves almost nothing for the KV
# cache, so this uses an L40S (48 GB). A100-40GB also works if L40S is queued.
GPU = "L40S"

app = modal.App("gemma-sglang")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("sglang[all]==0.4.6.post1", "huggingface_hub[hf_transfer]==0.30.2")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

# Weights are cached in a volume so restarts don't re-download ~19 GB.
hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)


@app.function(
    image=image,
    gpu=GPU,
    volumes={"/root/.cache/huggingface": hf_cache},
    secrets=[modal.Secret.from_name("huggingface")],
    timeout=60 * 60,
    scaledown_window=60 * 5,
    max_containers=1,
)
@modal.concurrent(max_inputs=8)
@modal.web_server(port=PORT, startup_timeout=60 * 20)
def serve():
    import subprocess

    cmd = [
        "python", "-m", "sglang.launch_server",
        "--model-path", MODEL_NAME,
        "--revision", MODEL_REVISION,
        "--host", "0.0.0.0",
        "--port", str(PORT),
        # Gemma-2 uses attention + final logit soft-capping and interleaved sliding-window
        # attention. SGLang needs the FlashInfer backend for those; it ships in
        # sglang[all] and is the default on L40S, but pin it so a backend change upstream
        # doesn't silently produce wrong logits — which would corrupt the refusal-mass measure.
        "--attention-backend", "flashinfer",
        # Gemma-2's trained context is 8192 tokens. Episodes run ~9 turns plus a battery
        # branch; if a long ladder ever overflows, the runner will 400 rather than
        # silently truncate the escalation.
        "--context-length", "8192",
        # logprobs: refusal-probability mass before commitment (§5)
        "--enable-return-logprob",
    ]
    subprocess.Popen(" ".join(cmd), shell=True)
