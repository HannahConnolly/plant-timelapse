---
name: lambda-sync
description: Check that the Gemini prompt/schema in src/services/genai.py and aws_lambda/gemini_report/lambda_function.py have not drifted apart, run the Lambda tests, and give the manual deploy steps. Use after editing either file, or when asked to deploy or sync the Lambda.
---

# lambda-sync

The Gemini prompt and response schema live in two places that must stay aligned, and the Lambda only changes when the file is pasted into the console. Run this after editing either file.

## 1. Compare the two copies

Read both files and compare these pairs:

| `src/services/genai.py` | `aws_lambda/gemini_report/lambda_function.py` |
| --- | --- |
| `prompt` | `PROMPT` |
| `RESPONSE_SCHEMA` | `RESPONSE_SCHEMA` |
| `model="gemini-2.5-flash"` | `GEMINI_MODEL` default |

These differences are intentional. Do not "fix" them:
- **Prompt wording:** the Lambda says the metrics "are averages over the last 24 hours". The Pi version doesn't, because `--ai` uses the UTC calendar day.
- **`PROGRESS_PROMPT`, the `progress` schema field, and the second photo:** Lambda only (weekly comparison).
- **Schema type names:** the Lambda uses upper-case REST names (`"OBJECT"`, `"STRING"`, `"ARRAY"`). The SDK in `genai.py` takes lower-case.

Anything else that differs is drift. Report each difference as intentional or drift, quoting both lines. If the user changed one side on purpose (a new field, reworded task), propose the matching edit to the other side. Don't apply it without asking.

Also check that any new schema field is read by `build_discord_embed` in the Lambda and by the Discord code in `src/services/discord_bot.py`, since an unused field never reaches the report.

## 2. Run the tests

```bash
source venv/bin/activate
pytest src/tests/test_lambda_gemini_report.py
pytest
```

Add or update a test in `test_lambda_gemini_report.py` when `lambda_function.py` behavior changed. AWS and HTTP calls are mocked there. Do not invoke the real function or call Gemini to test.

## 3. Deploy by hand

Claude can't deploy this. Give the user these steps, and say plainly that nothing is live until they do them:

1. Open the Lambda console, function `plant-gemini-report` (same region as the S3 bucket).
2. **Code** tab: replace the contents of `lambda_function.py` with the repo file.
3. Click **Deploy**.
4. Optional smoke test: **Test** tab, paste `aws_lambda/gemini_report/test_event.json` (edit the bucket and key to a photo from the last day, or `should_process` skips it). This posts to the real Discord webhook and calls Gemini.
5. Check CloudWatch logs for `Posted report for ...` after the next 22:05 photo.

Changes to environment variables (`TABLE_NAME`, `DEVICE_ID`, `PARAMETER_PREFIX`, `GEMINI_MODEL`) or the Lambda timeout are also console-only. The timeout must stay above the sum of `GEMINI_RETRY_DELAYS` plus the request timeouts.

## 4. Report

End with: drift found (or none), test result, and whether the deploy is still pending.
