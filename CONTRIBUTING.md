# Contributing to AI Executive Assistant

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+ (for frontend development)
- Git

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ai-executive-assistant.git
cd ai-executive-assistant
```

2. Create development environment:
```bash
cp .env.example .env
# Edit .env with development credentials
```

3. Start development stack:
```bash
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

4. Access services:
- PWA: http://localhost
- FastAPI: http://localhost:8000
- API Docs: http://localhost:8000/api/docs
- N8N: http://localhost:5678

## Code Style

### Python (Backend)

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use docstrings for all functions/classes

```python
def function_name(param: str, optional: int = 0) -> Dict[str, Any]:
    """
    Brief description of function.

    Args:
        param: Description of param
        optional: Description of optional param

    Returns:
        Description of return value
    """
    pass
```

### JavaScript (Frontend)

- Use ES6+ features
- Semicolons required
- 2-space indentation
- Use async/await over promises

### Docker

- Use multi-stage builds
- Minimize image size
- Include health checks
- Document exposed ports

## Pull Request Process

1. **Create a Branch**
```bash
git checkout -b feature/your-feature-name
```

2. **Make Changes**
- Write clean, documented code
- Add tests where applicable
- Update documentation

3. **Test Locally**
```bash
# Run tests (if available)
pytest backend/tests/

# Check Docker build
docker-compose build

# Verify deployment
./scripts/deploy.sh
```

4. **Commit**
```bash
git add .
git commit -m "feat: add new feature"
```

Use conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance

5. **Push and Create PR**
```bash
git push origin feature/your-feature-name
```

Create pull request on GitHub with:
- Clear description of changes
- Reference related issues
- Screenshots (if UI changes)

## Areas for Contribution

### High Priority

- [ ] Additional N8N workflow templates (Google Docs, Slack, etc.)
- [ ] Frontend UI/UX improvements
- [ ] Test coverage for FastAPI endpoints
- [ ] Performance optimizations (caching, indexing)
- [ ] Multi-user authentication system

### Medium Priority

- [ ] Additional LLM provider integrations (Anthropic, Google)
- [ ] Advanced RAG features (hybrid search, reranking)
- [ ] Mobile app (React Native)
- [ ] Monitoring dashboard
- [ ] Backup/restore UI

### Documentation

- [ ] Video tutorials
- [ ] Architecture diagrams
- [ ] Use case examples
- [ ] API client libraries
- [ ] Troubleshooting guides

## Reporting Issues

### Bug Reports

Include:
- Clear description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Docker version, etc.)
- Logs (docker-compose logs)

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternative solutions considered
- Impact/priority

## Code Review

All submissions require review. We use GitHub pull requests for this purpose.

Reviewers will check:
- Code quality and style
- Documentation completeness
- Test coverage
- Security implications
- Performance impact

## Security

**Do not** open public issues for security vulnerabilities.

Instead, email security@your-domain.com with:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

- GitHub Discussions: [link]
- Discord: [link]
- Email: contribute@your-domain.com

---

Thank you for contributing! 🚀
