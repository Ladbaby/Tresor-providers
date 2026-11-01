# Tresor providers

Recipes for the provider catalog in [Tresor](https://github.com/Ladbaby/Tresor).

A **recipe** is one JSON file describing everything Tresor needs to talk to a
provider: the endpoint, the API formats, the auth shape, and — where a provider
needs vendor-specific request shaping — the plugin package that does it. Tresor
fetches this index, shows what is available, and installs a provider in one step
instead of asking for a hand-written downstream, a hand-authored rule, and a
manually installed plugin.

```
index.json     the catalog Tresor reads
<id>.json      one recipe per provider
```

`index.json` is served from `main`, so a correction reaches users without a
release.

## Add a provider

1. Write `<id>.json`. Start from an existing recipe; the shape is
   `tresor-provider-v1`.
2. Pin the plugin package you need — a released asset URL and its SHA-256, never
   a branch or "latest".
3. Add the entry to `index.json`. Every field except `url` is copied from the
   recipe, so a regenerate-from-disk pass is easier than editing by hand:

   | field | from the recipe |
   |---|---|
   | `id`, `name`, `icon`, `version`, `summary` | same-named field |
   | `url` | `<base>/<id>.json` |
   | `features`, `min_version` | `requires.features`, `requires.min_version` |
   | `needs_plugins` | `plugins` is non-empty |

   Getting a field wrong costs only a wrong label in the catalog list — an install
   reads the recipe, not the entry.

## Rules

**No secrets.** A recipe is public, so it can contain a client id, an endpoint, a
scope — never a key or a client secret. Tresor rejects a profile containing a
credential-looking field, and the user supplies credentials at install time.

**Nothing mutable is pinned loosely.** Package URLs point at a versioned release
asset and carry a `sha256`. A floating `main` or `latest` URL would mean a recipe
silently changes what code it installs.

**Declare what the recipe needs.** `requires.features` and `requires.min_version`
let Tresor mark an entry unavailable — with a reason — instead of failing halfway
through an install. Feature names are the plugin host modules: `kv.v1`,
`wire.v3`, `crypto.v1`, `compress.v1`, and the hooks in a plugin manifest.

**Breaking changes get a new schema, not a new directory.** A recipe declares its
format in `schema` (`tresor-provider-v1`); a build that does not recognise a
schema refuses that recipe instead of guessing. Additive fields do not need a
bump. Bump `version` when a recipe's contents change; it is what tells a user
their installed copy is behind.

## Providers

| id | what it is |
|---|---|
| `alibaba-qwen-beijing` / `-hong-kong` / `-singapore` / `-us-virginia` | Alibaba Model Studio Qwen, per shared region endpoint. Keys are region-specific. |
| `anthropic-claude-api` | Claude over the native Messages API, pay as you go. |
| `deepseek` | DeepSeek; Anthropic Messages served under `/anthropic`. |
| `google-gemini-api` | The Gemini Developer API (AI Studio), native Gemini format. |
| `minimax-china` / `minimax-international` | MiniMax China and international endpoints. Separate keys. |
| `moonshot-kimi` | Moonshot Kimi (China platform); Anthropic under `/anthropic`. |
| `nvidia-nim` | NVIDIA NIM, OpenAI Chat Completions only. |
| `openai-chatgpt-api` | OpenAI's pay-as-you-go API, Chat Completions and Responses. |
| `openai-chatgpt-subscription` | ChatGPT subscription via the Codex backend. OAuth device flow, no API key. Needs the `codex` dialect package. |
| `openai-compatible-endpoint` | Any endpoint speaking the OpenAI Chat Completions API. No plugin, api_key auth — the simplest path, useful for verifying an install. |
| `opencode-go` | OpenCode's Go plan. |
| `opencode-zen` | OpenCode Zen, including the free models. Both OpenCode entries need the `opencode-go` plugin for its `x-opencode-*` headers, stable session ids, and free-tier tool stubs. |
| `tencent-hy` | Tencent HY via TokenHub. |
| `xai-grok-api` | xAI's pay-as-you-go Grok API. |
| `xai-grok-subscription` | Grok subscription over OAuth (authorization code + PKCE, OIDC discovery). |
| `xiaomi-mimo-api` / `-token-plan-china` / `-token-plan-europe` / `-token-plan-singapore` | Xiaomi MiMo pay-as-you-go, plus the token-plan regions. Separate keys. |
| `zai-glm-api` / `zai-glm-coding-plan` | Z.AI general API and the GLM Coding Plan, which uses different paths. |

Ids and file names are a slug of the display name, so the two cannot drift apart
in a way that is hard to spot; `index.json` is ordered by that name.

## License

MIT, matching Tresor.
