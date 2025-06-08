import os

SEARCH_DIR = ''
MODELS_BASE_DIR = './models/'
OUTPUT_DIR = './output/'
AST_DIR = MODELS_BASE_DIR + '/sherpa/sherpa-onnx-zipformer-zh-en-2023-11-22/'
TTS_DIR = MODELS_BASE_DIR + '/sherpa/kokoro-multi-lang-v1_0/'
LLM_PATH = MODELS_BASE_DIR + '/llm/qwen2.5-3b-instruct-q8_0.gguf'
JSON_PATH = OUTPUT_DIR + "json_results.json"
WORK_THREADS = os.cpu_count()
