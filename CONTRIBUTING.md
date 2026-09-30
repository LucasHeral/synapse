# Contributing to SYNAPSE

Thank you for your interest in contributing to **SYNAPSE**!

## 🛠️ Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/LucasHeral/synapse.git
   cd synapse
   ```

2. **Install dependencies with `uv`**:
   ```bash
   make install
   ```

3. **Install pre-commit hooks**:
   ```bash
   make precommit
   ```

4. **Run the local development server**:
   ```bash
   make dev
   ```

---

## 🧪 Testing & Code Quality

Before submitting a Pull Request, ensure that all checks pass locally:

```bash
# Run linters and formatters
make lint
make format

# Run test suite
make test
```

---

## 🔄 Pull Request Guidelines

1. Create a feature branch (`git checkout -b feat/my-new-feature`).
2. Make your changes adhering to `ruff` code formatting.
3. Ensure all pre-commit hooks pass.
4. Commit your changes with a clear commit message (`git commit -m "feat: add support for custom categories"`).
5. Push to your branch and open a Pull Request!
