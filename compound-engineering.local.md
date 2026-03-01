# Breach Pivot Dashboard Code Review Configuration

---
review_agents:
  - kieran-python-reviewer
  - security-sentinel
  - performance-oracle
  - architecture-strategist
  - agent-native-reviewer
  - learnings-researcher
---

## Context

This PR implements the complete Breach Pivot Dashboard (Phases 1-5) for the Ralph Monitoring risk management system. The implementation includes:

- **Dashboard Frontend:** Dash/Plotly-based interactive data visualization
- **Backend Services:** Query builders, data loaders, state management
- **Testing:** Comprehensive unit and integration tests
- **Security Fixes:** Resolution of P1 SQL injection and debug mode vulnerabilities
- **Performance Optimization:** Phase 5.2 critical performance and security fixes

### Key Areas for Review

1. **Python Code Quality:** State models, callbacks, database layer, query builders
2. **Security:** SQL injection prevention, input validation, authentication boundaries
3. **Performance:** Query optimization, caching strategies, data loading efficiency
4. **Architecture:** Component separation, state management, callback patterns
5. **Agent Compatibility:** Dashboard state and data structures should be agent-accessible

### Files of Focus

- `src/monitor/dashboard/*.py` - Core dashboard modules
- `src/monitor/consolidate.py` - Parquet consolidation logic
- `tests/dashboard/*.py` - Test coverage
- `src/monitor/cli.py` - CLI integration
