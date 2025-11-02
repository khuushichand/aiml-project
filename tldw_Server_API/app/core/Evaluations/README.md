# tldw Evaluations Module

> Deprecation Notice (CLI)
>
> The legacy CLI at `tldw_Server_API/app/core/Evaluations/cli/evals_cli.py` is deprecated.
> Please use the unified CLI exposed via the console script `tldw-evals`,
> or run it directly with `python -m tldw_Server_API.cli.evals_cli`.
> The unified CLI includes health/status, evaluation execution, database/config
> management, users, webhooks, testing utilities, and export/import commands.

A comprehensive, modular evaluation system for benchmarking language models with support for standard benchmarks, custom evaluations, and advanced analysis tools.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -e ".[evals]"

# Check installation
tldw-evals health

# List available benchmarks
tldw-evals list-benchmarks

# Run your first evaluation
tldw-evals run simple_bench --limit 10
```

## 📋 Features

### Core Capabilities
- ✅ **Pre-configured Benchmarks**: MMLU Pro, GPQA, Simple Bench, and more
- ✅ **Custom QA Benchmarks**: Easy-to-create personal evaluation sets
- ✅ **Token Analysis**: WordBench for next-token prediction analysis
- ✅ **Multiple Scoring Methods**: Exact match, similarity, LLM judge
- ✅ **Flexible Data Loading**: JSON, JSONL, CSV, HuggingFace datasets
- ✅ **Comprehensive Analysis**: Metrics, categories, difficulty levels
- ✅ **CLI & API Access**: Command-line interface and programmatic usage
- ✅ **Extensible Architecture**: Easy to add new evaluation types

### Supported Benchmarks

| Benchmark | Type | Description |
|-----------|------|-------------|
| **SimpleQA** | Factuality | OpenAI's 4.3K short-form factuality questions |
| **MMLU Pro** | Multiple Choice | 12K questions, 10 options, reasoning-focused |
| **GPQA Diamond** | Multiple Choice | Graduate-level science questions |
| **Simple Bench** | Multiple Choice | Reasoning problems with scenarios |
| **BFCL** | Function Calling | Berkeley Function Calling Leaderboard |
| **SWE-bench** | Code Generation | Software engineering tasks |
| **MASK** | Honesty | Model honesty evaluation |
| **WordBench** | Token Analysis | Next-token prediction analysis |
| **Custom QA** | Question-Answer | Your own evaluation sets |

### Unified Evaluation Types (API)

The unified evaluation API supports multiple evaluation modes beyond benchmarks. Newly added types include:

- label_choice: Multi-class single-label selection where the model must return one label from an allowed set. Structured JSON output is supported by setting `eval_spec.structured_output=true` (returns `{ "label": "..." }`).
- nli_factcheck: Factual claims checking using NLI-style labels (e.g., SUPPORTED, REFUTED, NEI). Also supports structured JSON output with the same mechanism.

#### OCR (Text Extraction Quality)

Evaluate OCR effectiveness for designated documents by comparing OCR-extracted text to ground-truth.

- Endpoint: `POST /api/v1/evaluations/ocr`
- Request shape:
```json
{
  "items": [
    { "id": "doc1", "extracted_text": "...", "ground_truth_text": "..." }
  ],
  "metrics": ["cer", "wer", "coverage", "page_coverage"],
  "ocr_options": { "ocr_backend": "tesseract", "ocr_mode": "fallback" }
}
```

Metrics returned:
- `cer`: Character Error Rate
- `wer`: Word Error Rate
- `coverage`: |extracted| / |ground truth|
- `page_coverage`: fraction of pages with sufficient OCR text (if available)

Notes:
- For end-to-end OCR on PDFs, use the PDF processing API to extract text, then feed the result here alongside the ground truth.

#### SimpleQA Verified (Local Dataset)

Support added for a curated SimpleQA Verified dataset stored in the repo at `Helper_Scripts/Evals/SimpleQA_verified/`.

- Registry key: `simpleqa_verified`
- Loader auto-detects `.jsonl` or `.json` within that directory (prefers files with `verified` in the name)
- Usage via CLI or programmatic APIs that reference benchmarks:

```bash
tldw-evals run simpleqa_verified --limit 100
```

Or via the registry programmatically:

```python
from tldw_Server_API.app.core.Evaluations.benchmark_registry import get_registry

reg = get_registry()
evaluator = reg.create_evaluator("simpleqa_verified")
data = reg.load_dataset("simpleqa_verified", limit=100)
# ... run evaluation using your model and evaluator
```

Sample dataset items:

```json
// label_choice
{
  "input": {
    "question": "What color is the sky at noon?",
    "context": "Assume clear weather.",
    "allowed_labels": ["BLUE", "RED", "GREEN"]
  },
  "expected": { "label": "BLUE" }
}
```

```json
// nli_factcheck
{
  "input": {
    "claim": "The Eiffel Tower is in Berlin.",
    "evidence": "The Eiffel Tower is a landmark in Paris, France.",
    "allowed_labels": ["SUPPORTED", "REFUTED", "NEI"]
  },
  "expected": { "label": "REFUTED" }
}
```

Key `eval_spec` fields:

- `allowed_labels`: canonical labels
- `label_mapping`: map aliases to canonical labels (e.g., {"ENTAILMENT":"SUPPORTED"})
- `structured_output`: if true, the model is prompted to return strict JSON `{ "label": "..." }`
- `generate_predictions`: if false, expects `input.prediction` instead of calling an LLM
- `prompt_template`: optional override with format variables depending on type

### Supported LLM Providers
- OpenAI
- Anthropic
- Google (Gemini)
- Cohere
- DeepSeek
- Groq
- HuggingFace
- Local models (Llama.cpp, Ollama, etc.)
- Any OpenAI-compatible API

## 📁 Module Structure

```
Evaluations/
├── cli/                    # CLI interface
│   ├── evals_cli.py       # Main CLI entry point
│   └── benchmark_cli.py   # Benchmark commands
├── configs/               # Benchmark configurations
│   ├── mmlu_pro.yaml
│   ├── simple_bench.yaml
│   ├── wordbench.yaml
│   └── simple_qa_template.yaml
├── data/                  # Example datasets
│   └── example_qa_questions.json
├── benchmark_utils.py     # Base evaluation classes
├── benchmark_registry.py  # Benchmark management
├── benchmark_loaders.py   # Dataset loading utilities
├── evaluation_manager.py  # Result storage and analysis
├── qa_benchmark_helper.py # QA benchmark utilities
└── wordbench_runner.py   # WordBench implementation
```

## 🎯 Usage Examples

### Running Pre-configured Benchmarks

```bash
# Run MMLU Pro with 100 questions
tldw-evals run mmlu_pro --limit 100 --output mmlu_results.json

# Run with specific API
tldw-evals run simple_bench --api anthropic --api-key YOUR_KEY

# Resume interrupted evaluation
tldw-evals run gpqa --resume-from partial.json

# Validate benchmark before running
tldw-evals validate mmlu_pro --samples 5
```

### Creating Custom QA Benchmarks

#### Method 1: Quick Start with Python
```python
from qa_benchmark_helper import QADatasetBuilder, QAEvaluation

# Create dataset
qa_pairs = [
    ("What is the capital of France?", "Paris"),
    ("Who wrote '1984'?", "George Orwell"),
    ("What is 2 + 2?", "4")
]

dataset = QADatasetBuilder.create_from_pairs(qa_pairs, category="general")
QADatasetBuilder.save_dataset(dataset, "my_benchmark.json")

# Run evaluation
evaluator = QAEvaluation(scoring_method="exact_match")
# ... evaluate model responses
```

#### Method 2: YAML Configuration
```yaml
# my_benchmark.yaml
name: my_knowledge_test
description: Personal knowledge benchmark
evaluation_type: qa_evaluation
dataset_source: ./data/my_questions.json
evaluation_params:
  scoring_method: llm_judge
```

#### Method 3: Direct JSON
```json
{
  "questions": [
    {
      "question": "What is machine learning?",
      "answer": "A subset of AI that enables systems to learn from data",
      "category": "AI",
      "difficulty": "easy"
    }
  ]
}
```

### Using WordBench for Token Analysis

```python
from wordbench_runner import WordBenchRunner

# Initialize runner
runner = WordBenchRunner(api_name="openai")

# Analyze prompts
prompts = [
    "The sky is",
    "Once upon a time",
    "The capital of France is"
]

results = await runner.run_benchmark(prompts, output_file="token_analysis.json")

# View probability distributions
for result in results:
    print(result["display"])
```

### Programmatic Usage

```python
from benchmark_registry import get_registry
from evaluation_manager import EvaluationManager

# Get registry
registry = get_registry()

# List benchmarks
benchmarks = registry.list_benchmarks()
print(f"Available: {benchmarks}")

# Load dataset
dataset = registry.load_dataset("simple_bench", limit=10)

# Create evaluator
evaluator = registry.create_evaluator("simple_bench")

# Run evaluation
manager = EvaluationManager()
# ... perform evaluation
```

## 🛠️ Installation

### Basic Installation
```bash
pip install -e ".[evals]"
```

### With Optional Dependencies
```bash
# For HuggingFace datasets
pip install datasets

# For semantic similarity scoring
pip install sentence-transformers

# For advanced analysis
pip install scikit-learn scipy
```

### Development Installation
```bash
# Clone repository
git clone https://github.com/your-repo/tldw_server
cd tldw_server

# Install with dev dependencies
pip install -e ".[dev,evals]"

# Run tests
pytest tests/Evaluations/ -v
```

## 📊 Understanding Results

### Result Structure
```json
{
  "benchmark": "benchmark_name",
  "num_samples": 100,
  "results": [...],
  "summary": {
    "average_score": 0.85,
    "by_category": {...},
    "by_difficulty": {...}
  }
}
```

### Key Metrics
- **Accuracy**: Percentage of correct answers
- **Average Score**: Mean score across all questions
- **Category Performance**: Breakdown by topic
- **Difficulty Analysis**: Performance by difficulty level
- **Entropy** (WordBench): Uncertainty in predictions
- **Concentration** (WordBench): How focused probability mass is

## 🔧 Configuration

### Environment Variables
```bash
export OPENAI_API_KEY=your_key
export ANTHROPIC_API_KEY=your_key
export EVALS_DEBUG=1  # Enable debug logging
```

### Config File
```yaml
# config.yaml
api_defaults:
  provider: openai
  temperature: 0.7
  max_tokens: 150

evaluation:
  parallel_workers: 4
  save_progress: true
  output_dir: ./results
```

## 📚 Documentation

- **[User Guide](EVALS_USER_GUIDE.md)**: Comprehensive user documentation
- **[Developer Guide](EVALS_DEVELOPER_GUIDE.md)**: Architecture and extension guide
- **[API Reference](api_reference.md)**: Complete API documentation

## 🧪 Testing

```bash
# Run all tests
pytest tests/Evaluations/

# Run specific test
pytest tests/Evaluations/test_benchmark_utils.py -v

# Run with coverage
pytest tests/Evaluations/ --cov=app.core.Evaluations --cov-report=html

# Run integration tests
pytest tests/Evaluations/ -m integration
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md).

### Adding a New Benchmark

1. Create evaluation class (if needed)
2. Add configuration in `configs/`
3. Provide dataset or loader
4. Write tests
5. Update documentation
6. Submit pull request

### Development Workflow

```bash
# Create feature branch
git checkout -b feature/new-benchmark

# Make changes
# ... edit files ...

# Run tests
pytest tests/

# Format code
black app/core/Evaluations/

# Submit PR
git push origin feature/new-benchmark
```

## 📊 Performance

### Optimization Tips
- Use `--parallel` for faster processing
- Enable `--save-progress` for long runs
- Use `--limit` for testing
- Stream large datasets to save memory

### Benchmarking Stats
- Process ~100 questions/minute (varies by model)
- Memory usage: ~500MB for typical benchmark
- Supports datasets up to 1M+ questions

## 🐛 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Import errors | `pip install -e ".[evals]"` |
| API key errors | Set environment variables or use `--api-key` |
| Memory issues | Use `--limit` or enable streaming |
| Slow evaluation | Increase `--parallel` workers |

### Debug Mode
```bash
# Enable debug logging
export EVALS_DEBUG=1
tldw-evals run benchmark --log-level DEBUG
```

## 📝 License

This module is part of tldw_server and is licensed under the GNU General Public License v2.0.

## 🙏 Acknowledgments

- Benchmark datasets from respective creators
- Community contributors
- Open source libraries used

## 📮 Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Email**: support@example.com

## 🗺️ Roadmap

- [ ] Additional benchmark support (IFEval, etc.)
- [ ] Web UI for evaluation management
- [ ] Real-time evaluation monitoring
- [ ] Model comparison tools
- [ ] Advanced statistical analysis
- [ ] Automated benchmark creation from documents
- [ ] Multi-modal evaluation support

---

Built with ❤️ for the AI evaluation community
