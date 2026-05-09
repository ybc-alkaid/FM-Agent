# Verification Failure Notes

This note records three pipeline issues observed during the SM crypto run, the useful log evidence, and the fixes applied or intentionally deferred.

## 1. Verification count was short after OpenRouter 503

Symptom:

```text
Functions pending verification: 5
```

Only four terminal result lines appeared before the pipeline advanced to the next layer.

Relevant log:

```text
2026-05-08 18:12:55,793 [INFO] Submitted: ../sm-crypto/fm_agent/extracted_functions/src/sm2/index-js/arrayToHex.js
2026-05-08 18:13:02,938 [INFO] HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 503 Service Unavailable"
2026-05-08 18:13:05,171 [INFO] HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 503 Service Unavailable"
2026-05-08 18:13:10,249 [INFO] HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 503 Service Unavailable"
2026-05-08 18:13:11,804 [ERROR] Error verifying ../sm-crypto/fm_agent/extracted_functions/src/sm2/index-js/arrayToHex.js: Error code: 503 - {'type': 'https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1102/', 'title': 'Error 1102: Worker exceeded resource limits', 'status': 503, 'detail': 'A Worker script configured by the website owner exceeded its resource limits (CPU time or memory) and was terminated.', ...}
```

Root cause:

The immediate trigger was an OpenRouter / Cloudflare 503. The pipeline bug was that a file was added to `processed` before its verification future completed. When the future raised, the error was only logged, no result JSON was written, and the layer could still be considered complete.

Fix:

- Keep rate-limit handling long: `RateLimitError` retries up to 20 times.
- Retry other transient LLM/OpenRouter failures up to 5 times with exponential backoff.
- Write a `verdict: "ERROR"` result JSON if verification ultimately fails.
- Move `processed.add(...)` until after the verification future returns a verdict.

## 2. Verification count was short after malformed upstream response

Symptom:

```text
Functions pending verification: 7
```

Only six terminal result lines appeared before the pipeline advanced.

Relevant log:

```text
2026-05-08 18:27:22,382 [INFO] Submitted: ../sm-crypto/fm_agent/extracted_functions/src/sm2/ec-js/isInfinity.js
2026-05-08 18:27:38,391 [ERROR] Error verifying ../sm-crypto/fm_agent/extracted_functions/src/sm2/ec-js/isInfinity.js: Expecting value: line 3 column 1 (char 11)
```

Relevant trace event:

```text
event_id: llm_d3f9167a3c864ccc9489db46db8e7580
status: error
summary: LLM implication check failed: Expecting value: line 3 column 1 (char 11)
purpose: check_post_implies_spec
function_id: src::sm2::ec-js::isInfinity
```

Root cause:

The model was not asked to output JSON for this step. The implication check expects tagged text such as `[CHECK_START]... [CHECK_END]`. The error happened before a usable assistant response was recorded, likely while the OpenAI SDK was parsing a malformed, empty, truncated, or non-JSON upstream response from OpenRouter. This is another upstream failure, but the same local `processed` timing bug made it disappear from the terminal count and result files.

Fix:

Same as issue 1: retry transient LLM errors, write an `ERROR` result after final failure, and only mark files processed after a verdict is returned.

## 3. No-spec output looked like a successful result

Symptom:

The watcher printed green check output for files that still lacked `[SPEC]` / `[INFO]` blocks, for example:

```text
[7/7] fm_agent/extracted_functions/src/sm4/index-js/hexToArray_2.js: ✔ (no spec)
Functions to reason about: 7
```

Root cause:

When OpenCode exited while some expected files were still not ready, the watcher printed them as green `(no spec)`. This did not lose work because the main loop still treats those files as pending and retries their batches, but the terminal output made the state look complete.

Fix:

- Rename the watcher header from `Functions to reason about` to `Functions pending verification`.
- When a retry invocation has already processed some files, print `Functions pending verification: <remaining> of <total>`.
- Change no-spec output from a green check to:

```text
[pending] <path>: no spec yet; will retry
```

No result JSON is written for no-spec files yet, because they are expected to receive specs on a later retry and then proceed through normal verification.

