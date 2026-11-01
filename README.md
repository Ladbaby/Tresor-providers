# Tresor providers

Recipes for the provider catalog in [Tresor](https://github.com/Ladbaby/Tresor).

A **recipe** is one JSON file describing everything Tresor needs to talk to a
provider: the endpoint, the API formats, the auth shape, and — where a provider
needs vendor-specific request shaping — the plugin package that does it. Tresor
fetches this index, shows what is available, and installs a provider in one step
instead of asking for a hand-written downstream, a hand-authored rule, and a
manually installed plugin.

```
index.json          the catalog Tresor reads
v1/<id>.json        one recipe per provider
```

`index.json` is served from `main`, so a correction reaches users without a
release. The `digest` on each entry is what makes that safe: Tresor hashes the
recipe it downloads with the same canonicalization that produced the digest, and
refuses the profile if they differ.

## Add a provider

1. Write `v1/<id>.json`. Start from an existing recipe; the shape is
   `tresor-provider-v1`.
2. Pin the plugin package you need — a released asset URL and its SHA-256, never
   a branch or "latest".
3. Compute the recipe digest and add the entry to `index.json`:

   ```bash
   # from a Tresor checkout
   go run ./zz_local_digest <this repo>/v1
   go run ./zz_local_catalog <this repo>/index.json <this repo>
   ```

   The second command validates the whole index — ids, versions, digests, HTTPS,
   and that every entry matches the recipe on disk.

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

**Do not version a recipe in place once it has shipped a breaking change.** New
fields go in a new `vN/` directory. Old Tresor builds never read the directory
they do not know about, so a newer recipe cannot break a build that cannot
understand it.

## Providers

| id | what it is |
|---|---|
| `chatgpt` | ChatGPT subscription via the Codex backend. OAuth device flow, no API key. Needs the `codex` dialect package. |
| `opencode` | OpenCode Zen, including the free models. Needs the `opencode-go` plugin for its `x-opencode-*` headers, stable session ids, and free-tier tool stubs. |
| `opencode-go` | OpenCode's Go plan. Same plugin, different gateway. |
| `openai-compatible` | Any endpoint speaking the OpenAI Chat Completions API. No plugin, api_key auth — the simplest path, useful for verifying an install. |

## License

MIT, matching Tresor.
