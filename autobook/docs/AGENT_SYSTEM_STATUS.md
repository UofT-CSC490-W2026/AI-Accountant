# Agent System Status

8-agent LLM pipeline (LangGraph + Claude Sonnet on Bedrock) is implemented and merged into `autobook`. Classifies transactions and generates double-entry journal entries with tax handling.

Stage 1 ablation complete on 15 basic test cases (textbook-level accounting questions). Best variant (`classify_and_build`) achieves 100% accuracy at ~$0.03/transaction. This is now the default config.

Waiting on intermediate and hard test cases (fuzzy descriptions, multi-line entries, real-world edge cases) to continue ablation and validate pipeline robustness.
