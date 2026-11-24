<!-- header:start -->
<div align="center">

<img src="./assets/banner.svg" alt="HintForge" width="100%">

<a href="#-quick-start"><img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=20&pause=1000&color=00ff9f&center=true&vCenter=true&width=640&lines=Forgot+the+password%3F;Describe+what+you+remember;AI+forges+likely+keys" alt="Forgot the password? · Describe what you remember · AI forges likely keys"></a>

<a href="LICENSE"><img src="https://img.shields.io/github/license/ajendras/hintforge?style=for-the-badge&color=ff0044" alt="License"></a>
<img src="https://img.shields.io/badge/Python-ff0044?style=for-the-badge&logo=python&logoColor=white" alt="Python">
<a href="https://github.com/ajendras/hintforge/stargazers"><img src="https://img.shields.io/github/stars/ajendras/hintforge?style=for-the-badge&logo=github&color=00ff9f" alt="Stars"></a>
<a href="https://github.com/ajendras/hintforge/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/ajendras/hintforge/ci.yml?style=for-the-badge&label=CI" alt="CI"></a>
<img src="https://img.shields.io/github/last-commit/ajendras/hintforge?style=for-the-badge&color=ff0044" alt="Last commit">
<a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/PRs-welcome-22c55e?style=for-the-badge" alt="PRs welcome"></a>

**AI-powered contextual password recovery for ZIP, RAR, PDF, 7z, TAR and Office (docx/xlsx) documents**

[✨ Features](#-features) • [⚡ Quick start](#-quick-start) • [🧰 Usage](#-usage) • [🧩 Architecture](#-architecture) • [📍 Roadmap](#-roadmap) • [🤝 Contributing](#-contributing)

</div>
<!-- header:end -->

## ✨ Why HintForge?

People regularly forget passwords to their own archives. Brute-force and plain dictionary attacks are too slow or ineffective against modern encryption. HintForge fills the gap by using a local LLM (via Ollama) to convert vague user memories like "my dog + birth year" into intelligently ranked password candidates.

- **Context Oracle**: `generate_candidates()` turns natural-language hints into high-probability candidates using local models
- **Auto Context Extraction**: Pulls keywords from filename, nearby files (text/docs) and EXIF/PDF metadata to enrich the prompt automatically
- **Hybrid intelligence**: Combines AI guesses with `DictionaryStrategy`, `MaskStrategy`, `HashcatStrategy` (GPU) and rules before testing
- **Multi-format support**: Native handling for ZIP, RAR, PDF, 7z, TAR and Office (DOCX/XLSX) via `handlers.detect_format()` and `open_with_password()`
- **Safe & resumable**: Dry-run mode, non-destructive `try_password()`, session checkpoints in `.hintforge/`, and strength analysis
- **Brutalist live UI**: Real-time progress, ETA and chunky neo-brutalist panels built with Rich
- **GPU acceleration**: Optional Hashcat integration for mask and rule attacks when JohnTheRipper + hashcat are available
- **Web Dashboard**: Simple neo-brutalist Flask UI for launching and monitoring multiple recovery jobs
- **Plugin system**: Drop in Python files containing `generate(hint, **kwargs)` generator functions; automatically merged by the hybrid pipeline when listed in `plugin_paths`

## 🎬 Demo

<p align="center"><img src="./assets/demo.svg" alt="HintForge demo" width="760"></p>

## 🚀 Features

<table>
<tr>
<td>
🧠 <b>Context Oracle</b><br>
Local LLM converts hints into ranked <code>Candidate</code> objects
</td>
<td>
📁 <b>Auto Context</b><br>
Extracts keywords from filename, nearby files and EXIF/PDF metadata
</td>
<td>
📦 <b>Multi-Format</b><br>
Native support for ZIP, RAR, PDF, 7z, TAR and Office (DOCX/XLSX) documents
</td>
</tr>
<tr>
<td>
🔀 <b>Hybrid Attacks</b><br>
<code>run_strategy("hybrid")</code> merges AI, dictionary, mask and GPU hashcat candidates
</td>
<td>
📊 <b>Likelihood Ranking</b><br>
Scores candidates by LLM likelihood before expensive testing
</td>
<td>
📈 <b>Live Progress</b><br>
Neo-brutalist Rich UI with ETA, rate and chunky panels
</td>
</tr>
<tr>
<td>
🧩 <b>Pluggable Strategies</b><br>
Easy-to-extend <code>BaseStrategy</code> subclasses and registry (now with HashcatStrategy)
</td>
<td>
🛡️ <b>Safe Testing</b><br>
<code>--dry-run</code> and non-destructive validation via <code>tester.py</code>
</td>
<td>
⏳ <b>Session Resume &amp; Share</b><br>
Checkpoint/restore with <code>SessionState</code> JSON files. New <code>export</code> / <code>import</code> commands for sharing recovery state
</td>
</tr>
<tr>
<td>
🔎 <b>Strength Analyzer</b><br>
<code>analyze()</code> reports encryption strength and recommends strategy (including hashcat)
</td>
<td>
🔐 <b>Password Strength Estimator</b><br>
Built-in entropy calculation + crack-time projections (online/CPU/GPU) via <code>estimate_strength()</code>
</td>
<td>
🔬 <b>GPU Acceleration</b><br>
Hashcat integration (mask + rule attacks) via <code>HashcatStrategy</code> when <code>hashcat</code> and JohnTheRipper <code>*2john</code> tools are installed
</td>
</tr>
<tr>
<td colspan="3">
🌐 <b>Web Dashboard</b><br>
Simple neo-brutalist Flask UI (<code>hintforge dashboard</code>) for job creation, live monitoring and chunky progress
</td>
</tr>
<tr>
<td colspan="3">
🔌 <b>Plugin System</b><br>
User-supplied Python generator functions loaded from <code>plugin_paths</code>; merged into hybrid pipeline with <code>Candidate</code> scoring
</td>
</tr>
</table>

## 📦 Installation

Requires Python 3.9+ and a running Ollama instance (e.g. `llama3`). Office (docx/xlsx) support is available via the `[office]` extra. The web dashboard is available via the `[web]` extra.

```bash
pip install "git+https://github.com/ajendras/hintforge.git#egg=hintforge[office,web]"
ollama pull llama3
# Optional but recommended for GPU attacks:
# sudo apt install hashcat john  # or equivalent for your OS
```

The CLI is automatically installed via the `hintforge` entrypoint defined in `pyproject.toml`.

## ⚡ Quick start

```bash
hintforge recover archive.rar --hint "vacation 2022 and pet name" --model llama3
```

HintForge automatically augments your hint with context extracted from the filename, nearby files and any available EXIF/PDF metadata.

Or launch the brutalist web dashboard:

```bash
hintforge dashboard
# Open http://localhost:5000 in your browser
```

Or use the Python API exposed in `src/hintforge/__init__.py`:

```python
from hintforge import recover, extract_context, export_session, import_session, estimate_strength, load_plugin_generators
from hintforge.models import SessionState, StrengthReport

print(extract_context("protected.zip"))  # see auto-extracted terms

password = recover(
    archive_path="protected.zip",
    hint="my dog max born in 2019",
    model="llama3",
    max_candidates=75,
    dry_run=False,
    resume=False
)
print(password)

report: StrengthReport = estimate_strength("MaxTheDog2022!")
print(f"Strength: {report.strength} ({report.entropy_bits} bits)")

# Share recovery state
export_session("protected.zip", "team_session.json")
state: SessionState = import_session("team_session.json")
print(f"Imported session with {state.candidates_tested} candidates tested")
```

## 🧰 Usage

Generate candidates only (no archive required):

```bash
hintforge generate --hint "family vacation greece 2018" --count 40 --model llama3
```

When an `archive_path` is supplied to `generate_candidates()` the hint is automatically augmented with context from the filename, sibling files (.txt/.md content) and EXIF/PDF metadata.

Analyze encryption strength and get a recommendation:

```bash
hintforge analyze backup.7z --format 7z
```

Estimate password strength and crack-time projections:

```bash
hintforge strength "Vacation2022Max!"
```

Basic recovery with resume support:

```bash
hintforge recover documents.zip \
  --hint "our wedding year and dogs name" \
  --max-candidates 120 \
  --resume
```

Export and import sessions for collaboration, backup or moving between machines:

```bash
# Export current recovery state
hintforge export documents.zip --output team_session.json

# Import on another machine (optionally override archive path)
hintforge import team_session.json --archive /new/path/documents.zip

# Resume from the imported session
hintforge recover documents.zip --resume
```

Start the web dashboard (opens a neo-brutalist monitoring interface):

```bash
hintforge dashboard --port 8080
```

**Using the plugin system:**

Create a Python file (`my_generators.py`) with a generator function:

```python
from collections.abc import Iterator
from hintforge.models import Candidate

def generate(hint: str, **kwargs) -> Iterator[str | Candidate]:
    """User-supplied generator – can use hint, config, archive_path etc."""
    yield hint.replace(" ", "") + "2024!"
    yield "My" + hint.split()[0].capitalize() + "Pass123"
    yield Candidate(score=0.85, value="CustomPlugin2025", metadata={"source": "myplugin"})
```

Reference it in `config.toml` or on the CLI:

```bash
hintforge recover archive.rar --hint "vacation pet" --plugin my_generators.py
```

The hybrid strategy automatically includes yielded passwords (scored 0.6 by default) alongside AI/dictionary/mask/hashcat candidates. Multiple `--plugin` flags or a list in `plugin_paths` are supported.

When `hashcat` and JohnTheRipper tools are present and `hashcat` is listed in `enabled_strategies`, the hybrid pipeline automatically runs GPU-accelerated mask and rule attacks after the CPU strategies.

<details><summary>Advanced: custom config and strategy control</summary>

Create a `config.toml` (loaded by `utils.load_config()`):

```toml
model = "llama3"
max_candidates = 100
temperature = 0.7
enabled_strategies = ["ai", "dictionary", "mask", "hashcat", "plugin"]
min_score_threshold = 0.3
use_gpu = true
hashcat_mask = "?d?d?d?d?d?d?d?d"
plugin_paths = ["my_generators.py"]
online_guesses_per_second = 5
cpu_guesses_per_second = 1000000
gpu_guesses_per_second = 100000000
```

Then run a hybrid strategy directly from Python:

```python
from hintforge import run_strategy, Candidate, Config
from hintforge.models import Candidate

config = Config(max_candidates=50, model="llama3", enabled_strategies=["ai", "hashcat", "plugin"], plugin_paths=["my_generators.py"])
seed = [Candidate(score=0.9, value="Max2019!")]

candidates = run_strategy(
    strategy="hybrid",
    hint="our dog max vacation 2019",
    candidates=seed,
    config=config,
    archive_path="protected.rar"
)
print([c.value for c in candidates[:5]])
```
</details>

## 🔧 Configuration

| Option                        | Default       | Description                                      |
|-------------------------------|---------------|--------------------------------------------------|
| model                         | llama3        | Ollama model name (must be available locally)   |
| max_candidates                | 75            | Maximum candidates to generate and test          |
| temperature                   | 0.75          | LLM temperature for candidate diversity          |
| top_p                         | 0.9           | Nucleus sampling parameter                       |
| enabled_strategies            | ["ai", "dictionary", "mask", "hashcat", "plugin"] | Strategies used in hybrid mode |
| dictionary_path               | None          | Optional custom wordlist path                    |
| min_score_threshold           | 0.25          | Discard candidates below this score              |
| hashcat_path                  | hashcat       | Path to hashcat binary                           |
| use_gpu                       | true          | Use GPU devices (-D 2) for hashcat               |
| hashcat_mask                  | ?d?d?d?d?d?d?d?d | Default mask for mask-mode attacks          |
| plugin_paths                  | []            | List of paths to .py files exporting `generate(hint, **kwargs)` generators |
| online_guesses_per_second     | 5             | Guesses/sec used for online crack-time projection |
| cpu_guesses_per_second        | 1000000       | Guesses/sec used for CPU offline crack-time projection |
| gpu_guesses_per_second        | 100000000     | Guesses/sec used for GPU offline crack-time projection |

All values are defined in `models.Config` and loaded from `config.toml` by `utils.load_config()`. The built-in strength estimator uses the three speed parameters to project realistic crack times for archive-style hashes. Plugin modules are loaded with `importlib` and must export a callable named `generate` (or `generate_candidates`) that accepts a hint and yields strings or `Candidate` objects.

## 🧩 Architecture

```mermaid
flowchart TD
    CLI[cli.py<br>recover / analyze / generate / dashboard / export / import] --> Core[core.py<br>recover(), analyze(), session handling, export/import + job management]
    Core --> Oracle[oracle.py<br>generate_candidates() + extract_context()]
    Oracle --> Ollama[(Ollama<br>llama3)]
    Oracle --> FS[Filesystem<br>filename + nearby .txt/.md + EXIF/PDF metadata]
    Core --> Strategies[strategies.py<br>run_strategy("hybrid")]
    Strategies --> AIStrategy[AIStrategy]
    Strategies --> DictionaryStrategy[DictionaryStrategy]
    Strategies --> MaskStrategy[MaskStrategy]
    Strategies --> HashcatStrategy[HashcatStrategy<br>GPU mask/rule]
    Strategies --> PluginStrategy[PluginStrategy<br>user Python generators via load_plugin_generators()]
    Core --> Tester[tester.py<br>try_password()]
    Tester --> Handlers[handlers.py<br>detect_format() + open_with_password() + extract_hash()]
    Core --> Session[(SessionState<br>.hintforge/*.json<br>export/import)]
    Core --> Jobs[(Job<br>.hintforge/job-*.json)]
    Core --> Dashboard[dashboard.py<br>Flask brutalist UI]
    Core --> Utils[utils.py<br>load_config() + brutalist_panel() + sanitize_password() + run_hashcat() + load_plugin_generators() + job persistence]
    Handlers --> ZIP[RAR/PDF/7z/TAR/OFFICE handlers]
    Handlers --> John[JohnTheRipper *2john tools]
    Strategies --> Hashcat[hashcat binary (GPU)]
    Dashboard --> Browser[(Browser<br>neo-brutalist UI)]
```

The orchestrator in `core.py` coordinates the Context Oracle, pluggable strategies, tester facade and session persistence. All data flows through Pydantic `Candidate` and `Config` models, keeping the pipeline type-safe, resumable and easy to extend. The new dashboard provides a web front-end for job management using the same models. `extract_context()` automatically enriches every hint when an `archive_path` is supplied. Session export/import makes it trivial to share partial or complete recovery state. The plugin system lets users extend candidate generation by dropping in simple Python files; `PluginStrategy` discovers `generate()` callables via `load_plugin_generators()` and injects them into the hybrid flow with appropriate scoring.

## 📁 Project structure

```text
.
├── pyproject.toml                 # Metadata, dependencies, console_scripts entrypoint
├── config.toml                    # Default model, temperature, strategies, paths
├── src/hintforge/
│   ├── __init__.py                # Public API: recover, analyze, generate_candidates, run_strategy, Candidate, Job, run_dashboard, extract_context, export_session, import_session
│   ├── cli.py                     # Click commands + neo-brutalist Rich UI (_brutalist_header, HEAVY boxes)
│   ├── core.py                    # Orchestrator: recover(), analyze(), session handling, export/import + job management
│   ├── oracle.py                  # Ollama integration, JSON parsing, _parse_llm_response(), extract_context()
│   ├── strategies.py              # BaseStrategy, AIStrategy, DictionaryStrategy, MaskStrategy, HashcatStrategy, PluginStrategy, run_strategy()
│   ├── tester.py                  # try_password(), format-specific _test_* helpers
│   ├── handlers.py                # detect_format(), open_with_password(), extract_hash(), PasswordError (now with Office)
│   ├── models.py                  # Pydantic models: Candidate, Config, SessionState, Job (enhanced for dashboard)
│   ├── utils.py                   # load_config(), save_session(), brutalist_panel(), sanitize_password(), run_hashcat(), load_jobs(), save_job(), load_plugin_generators()
│   └── dashboard.py               # Brutalist Flask web UI + job creation/monitoring
├── tests/
│   ├── test_oracle.py             # Mocked Ollama responses, parsing and extract_context tests
│   └── test_tester.py             # Unit + integration tests with fixture archives (now includes hashcat mocks + session export/import + plugin tests)
├── examples/recovery_demo.py      # Runnable full-workflow example with test RAR
└── LICENSE
```

## 🧪 Testing

```bash
pytest -q
```

Tests cover candidate generation (mocked Ollama in `test_oracle.py`), password testing with real fixture archives (`test_tester.py`), core orchestration, strategy merging, format detection, hash extraction, session serialization **and the new export/import functionality and password strength estimator**. Run with the `[test]` extra. New tests validate `extract_context()` with temporary files and mocked EXIF as well as round-tripping of `SessionState` via export/import and entropy/crack-time calculations in `estimate_strength()`. The plugin system is exercised with temporary generator files and patched loaders.

## 📍 Roadmap

<!-- roadmap:start -->
- [x] **v0.1.0** — first release: Context Oracle, Multi-Format, Hybrid Attacks, Likelihood Ranking
- [x] Add Office document (docx/xlsx) handlers
- [x] Hashcat integration for GPU-accelerated mask and rule attacks
- [x] Simple brutalist web dashboard for job monitoring
- [x] Auto-extract context from filename, nearby files and EXIF
- [x] Session export/import for sharing recovery state
- [x] Built-in password strength estimator with crack-time projection
- [x] Plugin system for user-supplied Python generators
- [ ] Parallel testing using ProcessPoolExecutor
- [ ] Support for 7z and OpenSSL-encrypted TAR files
- [ ] Verbose logging and JSON result export
- [ ] Pre-built common wordlists with frequency ranking
- [ ] Interactive hint refinement loop based on partial matches

> 🤖 This roadmap is worked through continuously — ideas and PRs welcome!
<!-- roadmap:end -->

## 🤝 Contributing

We love loud, chunky contributions! Please read [CONTRIBUTING.md](https://github.com/ajendras/hintforge/blob/main/CONTRIBUTING.md) and adhere to our [Code of Conduct](https://github.com/ajendras/hintforge/blob/main/CODE_OF_CONDUCT.md).

PRs improving the neo-brutalist UI, adding new format handlers, or extending strategies are especially welcome. Look for issues labeled `good-first-issue`.

## 📄 License

[MIT License](LICENSE) — see the full text for details.

<!-- footer:start -->
<div align="center">

### ⭐ Star history

<a href="https://star-history.com/#ajendras/hintforge&Date"><img src="https://api.star-history.com/svg?repos=ajendras/hintforge&type=Date" alt="Star history" width="600"></a>

If **HintForge** saves you time, a ⭐ helps others find it.

Made with ❤️ by [Ajendra](https://ajendra.info)

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:ff0044,100:00ff9f&height=120&section=footer" width="100%" alt="">

</div>
<!-- footer:end -->
