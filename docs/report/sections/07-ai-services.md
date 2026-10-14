# 7. Managed AI Services and the Free-Plan Fallback

## 7.1 Design

| Service | Role | Why it was chosen |
| --- | --- | --- |
| **Amazon Textract** (`StartDocumentTextDetection` / `GetDocumentTextDetection`) | OCR: turns any PDF – including a scanned image – into lines of text | Reads multi-page PDFs directly from S3 with no PDF library in Lambda; the asynchronous API is needed because the synchronous call accepts only single-page documents. The processor polls every 3 s and stops 15 s before the Lambda timeout. |
| **Amazon Comprehend** (`DetectKeyPhrases`, `DetectEntities`) | NLP: key phrases and ORGANIZATION / DATE / TITLE entities | Pre-trained models – nothing to train or host. Text is sent in chunks of at most 5,000 UTF-8 bytes, split on line boundaries, with each entity's offset mapped back to the full text. |

Both are pay-per-call services with free allowances far above this project's usage (about 60
pages and 60 calls for the whole test campaign).

## 7.2 What happened on the project account

The AWS account used for the project was created on AWS's newer **Free plan**. On that plan both
services refused every call with:

```
SubscriptionRequiredException: The AWS Access Key Id needs a subscription for the service
```

This is an account-level restriction, not a permission or code error – the IAM role allowed both
actions. Upgrading to a paid plan would have removed it, but the team kept the Rs. 0 guarantee and
designed a fallback instead.

## 7.3 The fallback

The processor now treats both services as preferred-but-optional:

1. It calls Textract first. If the call fails with `SubscriptionRequiredException`,
   `AccessDeniedException` or `UnrecognizedClientException`, it logs one warning, remembers the
   fact for the rest of the warm container and **reads the PDF's embedded text layer** with
   `pypdf`, a pure-Python library bundled into the deployment zip.
2. It calls Comprehend; on the same errors it logs one warning and scores on the extracted text
   alone. The skill dictionary and the date-range parser already work on plain text, so the score
   is unchanged for normal resumes.
3. A PDF with **no text layer** (a scanned image) cannot be read without OCR. It is marked
   `FAILED` with the reason *"no text layer in the PDF (scanned image); OCR needs Textract, which
   this AWS account cannot use"*, which the recruiter and the candidate both see.

An environment variable `TEXT_SOURCE` (`auto` / `textract` / `pdftext`) selects the behaviour;
`auto` is the default. On an account with access, **the same code uses Textract and Comprehend
with no change**.

| Resume type | With Textract access | On the Free plan (as deployed) |
| --- | --- | --- |
| Text PDF (Word, Google Docs, LaTeX) | OCR text | PDF text layer – same score |
| Two-page PDF | all pages | all pages (R6 scored 100) |
| Scanned image PDF | OCR text | `FAILED` with a clear reason (R3) |

This turned a blocked dependency into a documented, tested degradation path: five of the six test
resumes score exactly as designed, and the sixth demonstrates the failure handling required by the
blueprint (T1.6).
