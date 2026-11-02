# Keyword Tab Search

Type a search engine's keyword in Zen's address bar, press **Tab**, then enter
your query and press **Enter**. For example, a saved `cr` keyword becomes:

```text
cr → Tab → search terms → Enter
```

Version **0.1.0** uses Zen's native search mode. It reads your existing visible
engines and aliases, including plain versions of built-in `@` aliases. It does
not change engine definitions or construct replacement search URLs.

Only exact, case-insensitive keywords are activated. An explicitly configured
plain keyword takes precedence over a name derived from `@keyword`. Ambiguous
keywords do not activate an engine. An unrecognized keyword, Shift+Tab, modified
Tab, text composition, and Tab in page forms retain their normal behavior.

Engine additions, removals, and keyword changes refresh automatically. Disable
the mod in Sine to remove the behavior. Ordinary keyword-plus-Space searching
continues to use Zen's native handling.

## Install on macOS or Windows

Follow the collection's [installation guide](../README.md#install-the-sine-mods).
Use this subfolder URL in Sine:

```text
https://github.com/toby-wong/sine-mods/tree/main/keyword-tab-search
```

For a local checkout, select `--mods keyword-tab-search` with the shared
installer after closing Zen. Restart Zen after installation.

The keyboard handling is the same on macOS and Windows. Live validation is
performed on macOS; native Windows input requires separate validation.

## Development

```sh
node --test keyword-tab-search/tests/keyword-tab-search.test.cjs
```

See [AGENTS.md](AGENTS.md) for implementation constraints and current validation.
