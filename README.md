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
3. If the vendor sells the same provider at several endpoints, declare
   `provider.regions` instead of writing one recipe per endpoint (see
   [Regions](#regions)).
4. Add the entry to `index.json`. Every field except `url` is copied from the
   recipe, so a regenerate-from-disk pass is easier than editing by hand:

   | field | from the recipe |
   |---|---|
   | `id`, `name`, `icon`, `version`, `summary` | same-named field |
   | `url` | `<base>/<id>.json` |
   | `features`, `min_version` | `requires.features`, `requires.min_version` |
   | `needs_plugins` | `plugins` is non-empty |
   | `regions` | `provider.regions[]`, as `{id, name}` |

   `digest` is not a file hash: it is Tresor's canonical digest of the parsed
   profile, so reformatting a recipe does not change it. Take it from the
   regenerate pass rather than computing it by hand.

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

`regions` counts the endpoint choices the recipe offers.

| id | regions | what it is |
|---|---|---|
| `302ai` |  | 302.AI's relay. |
| `aihubmix` |  | AiHubMix's relay. |
| `qwen` | 13 | Alibaba's Qwen models on Model Studio and Qwen Cloud, plus the Token Plan subscriptions. Each region is a separate account with its own key, and a Token Plan's sk-sp- key is refused by the pay-as-you-go hosts. |
| `amazon-bedrock` | 10 | Amazon Bedrock's runtime, with a Bedrock API key: Anthropic models on the Messages API, the rest on Chat Completions. |
| `amazon-bedrock-mantle` | 17 | Amazon Bedrock's Mantle endpoint, on the same Bedrock API key. It lists its own models, including Mantle-only ones. |
| `anthropic-claude-api` |  | Claude models over Anthropic's native Messages API, pay as you go. |
| `baidu-qianfan` | 3 | Baidu Qianfan's Token Plans and pay-as-you-go API. |
| `cherryin` |  | Cherry Studio's CherryIN relay. |
| `clinepass` |  | Cline's plan for open coding models. |
| `command-code` |  | Command Code's Provider API. |
| `deepseek` |  | DeepSeek's own API. |
| `fireworks` |  | Fireworks AI's inference API for open models. |
| `google-gemini-api` |  | The Gemini Developer API from AI Studio. |
| `groq` |  | Groq's inference API on Chat Completions and Responses. It serves other makers' models as well as its own. |
| `huaweicloud-maas` | 2 | Huawei Cloud's ModelArts MaaS: the Token Plan subscription and its pay-as-you-go API. |
| `kilo-gateway` |  | Kilo Code's gateway, at the OpenRouter-style API its own clients use. |
| `lm-studio` |  | A local LM Studio server on its default port 1234. |
| `longcat` |  | Meituan's LongCat platform: chat and Responses under /openai/v1, Anthropic messages under /anthropic. |
| `mlx-serve` |  | A local MLX-Serve server on its default port 11234. |
| `minimax` | 2 | MiniMax's models. China and the international site are separate accounts with their own keys. |
| `mistral` |  | Mistral's own models over the Chat Completions API. |
| `modelscope` |  | ModelScope API-Inference, with a ModelScope access token as the key. |
| `moonshot-kimi` | 4 | Kimi models from Moonshot: the open platform in China and internationally, plus the Kimi Code membership's own hosts. Each is a separate account, and a Kimi Code key is refused by the open platform. |
| `nvidia-nim` |  | NVIDIA's hosted NIM endpoints. |
| `nous-portal` |  | Nous Research's Nous Portal: its Hermes models and other makers'. Model ids are vendor/model. |
| `ollama` |  | A local Ollama server on its default port 11434. |
| `ollama-cloud` |  | Ollama's hosted models, reached with an API key from ollama.com. |
| `openai-chatgpt-api` |  | OpenAI's pay-as-you-go API. Separate from a ChatGPT subscription. |
| `openai-chatgpt-subscription` |  | Sign in with a ChatGPT account and use the Codex backend your subscription already covers. |
| `openai-compatible-endpoint` |  | Any endpoint that speaks the OpenAI Chat Completions API. |
| `opencode-go` |  | OpenCode's Go plan, spoken to the way the OpenCode client does. |
| `opencode-zen` |  | OpenCode's pay-as-you-go gateway, spoken to the way the OpenCode client does. Includes the free models. |
| `openrouter` |  | OpenRouter's gateway: one key for many vendors' models. |
| `pipellm` |  | PipeLLM's relay: Chat Completions on its converter, GPT on Responses, Claude on Messages. |
| `siliconflow` | 2 | SiliconFlow's inference API. |
| `stepfun` | 4 | StepFun's Step models. |
| `tencent-tokenhub` | 3 | Tencent Cloud's TokenHub: the Token Plan subscription, and pay as you go. |
| `together-ai` |  | Together AI's inference API for open models. |
| `volcengine-ark` | 3 | Volcengine Ark: the Coding Plan, the Agent Plan, and pay as you go. |
| `xiaomi-mimo` | 4 | Xiaomi MiMo. |
| `zai-glm` | 4 | Z.ai's GLM models, sold as Zhipu in China: api.z.ai internationally and open.bigmodel.cn in China, each offering pay as you go and a Coding Plan at its own path on a key of its own. |
| `omlx` |  | A local oMLX server on its default port 8000. |
| `xai-grok-api` |  | xAI's pay-as-you-go Grok API, billed separately from a Grok subscription. |
| `xai-grok-subscription` |  | Sign in with an eligible Grok account and use the quota your subscription already covers. |
| `yylx` | 3 | yylx relay, with automatic, global and China endpoints. |

Ids and file names are a slug of the display name, so the two cannot drift apart
in a way that is hard to spot; `index.json` is ordered by that name.

## License

MIT, matching Tresor.
