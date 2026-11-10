# Groq model choice and evaluation plan

**Checked:** 6 November 2026  
**Status:** provisional selection; no task-specific Groq results have been measured yet.

## Recommendation

Start the fictional-data evaluation with `openai/gpt-oss-20b`, then compare it with `openai/gpt-oss-120b` using the same prompt and the same labelled cases. The smaller model is the low-cost baseline; the larger model is the quality challenger. Do not call either one “best quality” until the James test set shows that it links more cases correctly without adding wrong links.

I could not find Claude's model calculations in the repository. If you share that comparison, its assumptions and figures can be checked against this evaluation.

## Current listed GroqCloud rates

| Groq model ID | Status shown by Groq | Input / 1M tokens | Output / 1M tokens | Speed shown by Groq |
|---|---|---:|---:|---:|
| `openai/gpt-oss-20b` | Production | $0.075 | $0.30 | about 1,000 tokens/second |
| `openai/gpt-oss-120b` | Production | $0.15 | $0.60 | about 500 tokens/second |
| `qwen/qwen3.8-27b` | Preview | $0.80 | $4.00 | about 450 tokens/second |

Both GPT-OSS models are listed as supporting strict JSON Schema output on Groq. This matches James's need for a response shaped like `{"proposals": [...]}`. James should still run its own contract validation because valid JSON structure does not prove that a sample link is correct. Groq labels preview models as evaluation-only and warns they may be discontinued at short notice, so Qwen 3.8 is not the first choice for this prototype test.

Sources: [Groq supported models and prices](https://console.groq.com/docs/models), [GPT-OSS 20B model details](https://console.groq.com/docs/model/openai/gpt-oss-20b), [GPT-OSS 120B model details](https://console.groq.com/docs/model/openai/gpt-oss-120b), [Groq structured outputs and supported models](https://console.groq.com/docs/structured-outputs).

## Illustrative cost arithmetic

Groq's listed model prices are per million input and output tokens. For an example request with 10,000 input tokens and 2,000 output tokens:

- GPT-OSS 20B: `(10,000 × $0.075 + 2,000 × $0.30) / 1,000,000 = $0.00135`
- GPT-OSS 120B: `(10,000 × $0.15 + 2,000 × $0.60) / 1,000,000 = $0.00270`

This is an example size, not a measured James request. Actual cost depends on how many rows are uncertain, the register size, prompt length, and generated answer length. The client logs Groq's reported token usage and estimates token cost for these two models. Groq's current list price can change, so the saved run should retain the date and model ID.

## How to decide quality versus cost

Run both models against the same prompt version and the same labelled fictional sets (`dev`, `dev2`, and `dev3`). Record for each model:

1. correct links;
2. wrong links (the highest-risk outcome);
3. correct abstentions and missed links;
4. how many uncertain rows were sent to the model;
5. input/output tokens, estimated cost and response time;
6. exact model ID, prompt version, date and code commit.

Keep the hold-out set untouched until the final candidate is chosen. Choose the cheaper model if its task results are comparable and it does not increase wrong links. Consider the larger model only if the measured improvement is meaningful for the inspectors and worth the extra cost. Human review remains required whichever model is used.

## Data handling gate

Use only the synthetic data in the repository until RVL and the coach approve a provider and specify which data may be sent. Groq states that inference inputs and outputs are not retained by default, but may be temporarily logged for reliability or abuse monitoring for up to 30 days; Zero Data Retention is available. Groq also states that retained customer data is stored in US-region GCP buckets. This needs to be reviewed by the responsible RVL contact before any real reports are sent.

Source: [Groq's data retention and location documentation](https://console.groq.com/docs/your-data). This summary does not replace the team's privacy/legal review or approval.
