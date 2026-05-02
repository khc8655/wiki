#!/usr/bin/env python3
"""
SiliconFlow API unified client.
Supports chat (LLM) and embedding calls with retry + rate-limit handling.
"""

import json
import os
import time
import requests
from typing import List, Dict, Optional, Any
from functools import lru_cache


BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_CHAT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_EMBED_MODEL = "BAAI/bge-large-zh-v1.5"

# Models by role
MODELS = {
    "annotator":      "Qwen/Qwen2.5-7B-Instruct",
    "query_expander":  "Qwen/Qwen2.5-7B-Instruct",
    "reranker":        "Qwen/Qwen2.5-7B-Instruct",
    "embedding":       "BAAI/bge-large-zh-v1.5",
    "column_mapper":   "Qwen/Qwen2.5-7B-Instruct",
    "fallback_heavy":  "THUDM/GLM-Z1-9B-0414",
}


def _get_api_key() -> str:
    return os.getenv("SILICONFLOW_API_KEY", "sk-obkmzlzcqcrczvjmnwvxcioyxlcsrrhvqaqzzofltdvupaip")


def _api_headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }


def chat(
    messages: List[Dict[str, str]],
    model: str = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    timeout: int = 120,
    max_retries: int = 3,
) -> Optional[str]:
    """Call chat completion. Returns content string or None on failure."""
    model = model or DEFAULT_CHAT_MODEL
    url = f"{BASE_URL}/chat/completions"

    for attempt in range(max_retries):
        try:
            r = requests.post(
                url,
                headers=_api_headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=timeout,
            )
            data = r.json()

            if r.status_code == 429:
                wait = float(data.get("retry_after", 5))
                print(f"[LLM] Rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue

            if r.status_code != 200:
                print(f"[LLM] API error {r.status_code}: {data.get('message', data)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None

            choice = (data.get("choices") or [{}])[0]
            content = choice.get("message", {}).get("content", "")
            return content.strip() if content else None

        except requests.Timeout:
            print(f"[LLM] Timeout (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
        except Exception as e:
            print(f"[LLM] Error: {e} (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None

    return None


def chat_json(
    messages: List[Dict[str, str]],
    model: str = None,
    temperature: float = 0.1,
    max_retries: int = 3,
) -> Optional[dict]:
    """Call chat and parse JSON response. Returns dict or None."""
    model = model or DEFAULT_CHAT_MODEL
    text = chat(messages, model=model, temperature=temperature, max_retries=max_retries)
    if not text:
        return None

    # Extract JSON from response (model may wrap in ```json blocks)
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array or object
        for (open_c, close_c) in [("[", "]"), ("{", "}")]:
            start = text.find(open_c)
            end = text.rfind(close_c)
            if start >= 0 and end > start:
                candidate = text[start:end+1]
                # Repair common issues: double commas, trailing commas
                import re
                candidate = re.sub(r',\s*,+', ',', candidate)  # double commas
                candidate = re.sub(r',\s*([]}])', r'\1', candidate)  # trailing commas
                candidate = re.sub(r'"([^"]*?)(\n)([^"]*?)"', r'"\1\\n\3"', candidate)  # unescaped newlines in strings
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
        print(f"[LLM] Failed to parse JSON: {text[:300]}")
        return None


def embed(
    texts: List[str],
    model: str = None,
    batch_size: int = 32,
    timeout: int = 60,
    max_retries: int = 3,
) -> Optional[List[List[float]]]:
    """
    Get embeddings for a list of texts.
    Returns list of vectors, or None on failure.
    """
    model = model or DEFAULT_EMBED_MODEL
    url = f"{BASE_URL}/embeddings"
    all_vectors = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        for attempt in range(max_retries):
            try:
                r = requests.post(
                    url,
                    headers=_api_headers(),
                    json={
                        "model": model,
                        "input": batch,
                        "encoding_format": "float",
                    },
                    timeout=timeout,
                )
                data = r.json()

                if r.status_code == 429:
                    wait = float(data.get("retry_after", 5))
                    print(f"[Embed] Rate limited, waiting {wait}s")
                    time.sleep(wait)
                    continue

                if r.status_code != 200:
                    print(f"[Embed] API error {r.status_code}: {data.get('message', data)}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None

                results = data.get("data", [])
                vectors = [r.get("embedding", []) for r in sorted(results, key=lambda x: x.get("index", 0))]
                all_vectors.extend(vectors)
                break

            except requests.Timeout:
                print(f"[Embed] Timeout batch {i}-{i+len(batch)}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
            except Exception as e:
                print(f"[Embed] Error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None

    return all_vectors


def test():
    """Quick connectivity test."""
    print("Testing chat...")
    r = chat([{"role": "user", "content": "回复: 你好, 我是鱼虾的知识库助手。仅回复这一句。"}],
             model=DEFAULT_CHAT_MODEL, max_tokens=50)
    print(f"  Chat: {r}")

    print("Testing embed...")
    r = embed(["视频会议安全保障方案"], model=DEFAULT_EMBED_MODEL)
    if r:
        print(f"  Embed: dim={len(r[0])} vector[:5]={r[0][:5]}")
    else:
        print("  Embed: FAILED")


if __name__ == "__main__":
    test()
