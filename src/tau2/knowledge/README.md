# Knowledge Retrieval

Domains with a knowledge base (currently just `banking_knowledge`) use a `--retrieval-config` flag that controls how the agent accesses the knowledge base.

```bash
tau2 run --domain banking_knowledge --retrieval-config <config_name> --agent-llm gpt-4.1 --user-llm gpt-4.1
```

If `--retrieval-config` is omitted for `banking_knowledge`, the default is **`AllTools`**: BM25 search, dense embedding search, and read-only shell (see below). Choose an offline-only config such as **`bm25`** if you want no API keys or sandbox.

### AllTools (`AllTools`)

| Tool | Role |
|------|------|
| `KB_search_bm25` | BM25 sparse retrieval; pass **`k`** (default 10) for result count |
| `KB_search_dense` | Dense embeddings; pass **`k`** (default 10); backend set via CLI |
| `shell` | Same read-only sandboxed shell as `terminal_use` |

Requirements: **sandbox-runtime** for `shell`, and an embedding API for dense search:

- **`--dense-embedding-type openai_api`** (default): uses OpenAI embeddings — set **`OPENAI_API_KEY`**. Default model: **`text-embedding-3-large`** (override with **`--dense-embedding-model`**).
- **`--dense-embedding-type openrouter`**: uses OpenRouter — set **`OPENROUTER_API_KEY`**. Default model: **`qwen3-embedding-8b`** (override with **`--dense-embedding-model`**).

## Retrieval Configs

| Config | Tools | Requirements |
|--------|-------|--------------|
| `no_knowledge` | None | None (offline) |
| `full_kb` | None | None (offline) |
| `golden_retrieval` | None | None (offline) |
| `grep_only` | `grep` | None (offline) |
| `bm25` | `KB_search` | None (offline) |
| `openai_embeddings` | `KB_search` | `OPENAI_API_KEY` |
| `qwen_embeddings` | `KB_search` | `OPENROUTER_API_KEY` |
| `terminal_use` | `shell` | `sandbox-runtime` (see below) |
| `terminal_use_write` | `shell` | `sandbox-runtime` (see below) |
| `AllTools` | `KB_search_bm25`, `KB_search_dense`, `shell` | BM25 offline + see AllTools section above |

The `bm25`, `openai_embeddings`, and `qwen_embeddings` configs can also be combined with:
- `_reranker` suffix — adds an LLM reranker postprocessor (requires `OPENAI_API_KEY`)
- `_grep` suffix — adds a `grep` tool
- Both (e.g. `openai_embeddings_reranker_grep`)

Note: `*_reranker` variants always require `OPENAI_API_KEY` for the pointwise LLM reranker, even when the base embedder uses a different provider (e.g. `qwen_embeddings_reranker` needs both `OPENROUTER_API_KEY` and `OPENAI_API_KEY`).

## Embedding Cache

Embedding-based configs (`openai_embeddings*`, `qwen_embeddings*`) cache document embeddings on disk at `data/.embeddings_cache` (gitignored). This avoids re-computing embeddings on repeated runs. The cache is automatically invalidated when document content changes.

## Additional Setup

### OpenRouter API Key

The `qwen_embeddings*` configs route through [OpenRouter](https://openrouter.ai/). Set the `OPENROUTER_API_KEY` environment variable (or add it to your `.env` file — see `.env.example`).

### sandbox-runtime

The `terminal_use`, `terminal_use_write`, and `AllTools` configs require [Anthropic's sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) for secure filesystem isolation:

```bash
npm install -g @anthropic-ai/sandbox-runtime@0.0.23
```

**macOS**: Also requires `ripgrep`:
```bash
brew install ripgrep
```

**Linux**: Also requires `ripgrep`, `bubblewrap`, and `socat`:
```bash
# Ubuntu/Debian
sudo apt-get install ripgrep bubblewrap socat
```
